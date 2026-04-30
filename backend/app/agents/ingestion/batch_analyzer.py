"""
DeepSeek Batch Analyzer: 负责超长小说的批量异步分析。
利用 DeepSeek Batch API 实现高并发、低成本的角色抽取与情节摘要。

1. 准备请求 (.jsonl)
2. 上传文件 (/v1/files)
3. 创建批处理任务 (/v1/batches)
4. 轮询状态并获取结果
"""

import json
import logging
import os
import asyncio
from typing import List, Dict, Any, Optional
import httpx
from app.config.settings import settings
from app.core.utils import extract_json
from app.db.repository import get_repository
from app.modules.vector_store import VectorStoreManager

logger = logging.getLogger("loom.batch_analyzer")

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# 强制要求结构化输出的指令
BATCH_ANALYSIS_PROMPT = """
你是一个专业的小说分析专家。请分析以下章节内容，并提取：
1. 本章出现的角色及其视觉特征（外貌、衣着、道具）。
2. 识别“状态变更事件” (State Change Events)：即角色形象发生的永久性或重大变化（如：毁容、断臂、更换核心装备）。
3. 本章情节核心摘要。

请务必以如下 JSON 格式返回结果：
{
  "summary": "一句话摘要",
  "characters": [
    {"name": "角色名", "appearance": "外貌描写", "clothing": "衣着", "tools": "道具"}
  ],
  "state_changes": [
    {"entity": "角色名", "type": "appearance_update", "new_trait": "新特征描述", "reason": "变更原因"}
  ]
}
"""

class ParallelAnalyzer:
    def __init__(self, session_id: str, provider: str = "deepseek", model: str = "deepseek-chat", analysis_prompt: str = ""):
        self.session_id = session_id
        self.provider = provider
        self.model = model
        self.analysis_prompt = analysis_prompt
        self.api_key = self._get_api_key()
        self.repository = get_repository()
        self.vector_store = VectorStoreManager(self.session_id)
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    def _get_api_key(self) -> str:
        if self.provider == "google":
            return settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else ""
        return settings.DEEPSEEK_API_KEY.get_secret_value() if settings.DEEPSEEK_API_KEY else ""

    async def run_parallel_analysis(self) -> str:
        """
        使用并行的标准 API 调用模拟 Batch 任务。支持 DeepSeek 和 Gemini。
        """
        chapters = self.repository.get_chapters(self.session_id)
        if not chapters:
            return "no_chapters"

        # 使用信号量控制并发
        max_concurrent = 15 if self.provider == "google" else 10
        semaphore = asyncio.Semaphore(max_concurrent) 
        total = len(chapters)
        completed = 0
        failed = 0
        
        batch_id = f"parallel_{self.session_id}"
        
        async def analyze_single(ch):
            nonlocal completed, failed
            async with semaphore:
                try:
                    if self.provider in ["google", "ollama"]:
                        # 使用 LangChain 支持 (Gemini 或 Ollama)
                        from app.core.engine import get_llm
                        llm = get_llm(self.provider, self.model)
                        res = await llm.ainvoke([
                            {"role": "system", "content": f"{BATCH_ANALYSIS_PROMPT}\n\n**User Custom Instructions**: {self.analysis_prompt}" if self.analysis_prompt else BATCH_ANALYSIS_PROMPT},
                            {"role": "user", "content": f"章节内容：\n{ch.content}"}
                        ])
                        # 构造 mock result_data 格式以复用 process_single_result
                        result_data = {
                            "choices": [{"message": {"content": res.content}}]
                        }
                    else:
                        # OpenAI / DeepSeek 兼容模式
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            headers = {"Authorization": f"Bearer {self.api_key}"}
                            base_url = "https://api.deepseek.com/v1" if "deepseek" in self.provider else DEEPSEEK_BASE_URL
                            res = await client.post(
                                f"{base_url}/chat/completions",
                                headers=headers,
                                json={
                                    "model": self.model,
                                    "messages": [
                                        {"role": "system", "content": f"{BATCH_ANALYSIS_PROMPT}\n\n**User Custom Instructions**: {self.analysis_prompt}" if self.analysis_prompt else BATCH_ANALYSIS_PROMPT},
                                        {"role": "user", "content": f"章节内容：\n{ch.content}"}
                                    ],
                                    "response_format": {"type": "json_object"}
                                }
                            )
                            res.raise_for_status()
                            result_data = res.json()
                    
                    await self.process_single_result(ch.index, result_data)
                    completed += 1
                    logger.info(f"✅ [{self.provider}-{self.session_id}] 章节 {ch.index} 分析成功 ({completed + failed}/{total}, 成功:{completed}, 失败:{failed})")
                except Exception as e:
                    failed += 1
                    logger.error(f"❌ [{self.provider}] 章节 {ch.index} 分析失败: {e} ({completed + failed}/{total}, 成功:{completed}, 失败:{failed})")
                    self.repository.update_status(self.session_id, ch.index, 3) # 3: 失败

        async def run_all():
            try:
                # 给整个批次一个总超时 (如 10 分钟)
                await asyncio.wait_for(asyncio.gather(*(analyze_single(ch) for ch in chapters)), timeout=600.0)
            except asyncio.TimeoutError:
                logger.error(f"❌ [{self.provider}] 批次分析超时，部分章节可能未处理。")
            except Exception as e:
                logger.error(f"❌ [{self.provider}] 批次运行异常: {e}")
            
        asyncio.create_task(run_all())
        return batch_id

    async def process_single_result(self, chapter_idx: int, result_data: Dict[str, Any]):
        """处理单条 API 返回结果并同步到数据库"""
        choices = result_data.get("choices", [])
        if not choices:
            raise ValueError("No choices in LLM response")
        
        content_str = choices[0].get("message", {}).get("content", "")
        if not content_str:
            raise ValueError("Empty content in LLM response")
            
        # 使用统一的 extract_json 提取并解析数据
        try:
            data = extract_json(content_str)
        except Exception as e:
            raise ValueError(f"Failed to extract JSON from LLM response: {str(e)}")

        # 1. 更新数据库状态与章节摘要
        self.repository.update_analysis_result(
            self.session_id,
            chapter_idx,
            status=2,
            summary=data.get("summary"),
        )
        
        # 2. 角色状态变更持久化
        state_changes = data.get("state_changes", [])
        for change in state_changes:
            entity = change.get("entity")
            new_trait = change.get("new_trait")
            if entity and new_trait:
                self.vector_store.add_character_trait(
                    name=entity,
                    trait={"appearance_update": new_trait, "reason": change.get("reason")},
                    chapter_idx=chapter_idx
                )

        # 3. 基础角色特征
        characters = data.get("characters", [])
        for char in characters:
            name = char.get("name")
            if name:
                self.vector_store.add_character_trait(name=name, trait=char, chapter_idx=chapter_idx)
                # 同时触发一次 registry 持久化 (IngestionService 的兼容逻辑)
                self._update_character_registry_file(name, char)

    def _update_character_registry_file(self, name: str, trait: Dict[str, Any]):
        """增量更新 character_registry.json 以便兼容 IngestionService 的加载逻辑"""
        path = os.path.join(settings.CHROMA_PERSIST_DIRECTORY, self.session_id, "character_registry.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        registry = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    registry = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"⚠️ 角色注册文件读取失败，将重建: {e}")
        
        if name in registry:
            registry[name].update(trait)
        else:
            registry[name] = trait
            
        with open(path, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)

    def get_full_registry(self) -> Dict[str, Any]:
        """从 JSON 文件加载完整的角色注册表"""
        path = os.path.join(settings.CHROMA_PERSIST_DIRECTORY, self.session_id, "character_registry.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def get_story_context(self) -> List[Dict[str, Any]]:
        """返回章节级摘要，供分镜节点构造长文本上下文。"""
        return self.repository.get_chapter_summaries(self.session_id)

    async def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """查询模拟任务的状态"""
        # 统计数据库中已处理的章节数
        chapters = self.repository.get_chapters(self.session_id)
        total = len(chapters)
        completed = len([c for c in chapters if c.processed_status == 2])
        failed = len([c for c in chapters if c.processed_status == 3])
        
        if total == 0:
            status = "initial"
        else:
            status = "processing" if (completed + failed) < total else "completed"
        return {
            "status": status,
            "request_counts": {
                "total": total,
                "completed": completed,
                "failed": failed
            }
        }

    async def download_results(self, output_file_id: str) -> List[Dict[str, Any]]:
        """下载并解析结果文件"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.get(f"{DEEPSEEK_BASE_URL}/files/{output_file_id}/content", headers=self.headers)
            res.raise_for_status()
            
            results = []
            for line in res.text.splitlines():
                if line.strip():
                    results.append(json.loads(line))
            return results

    async def finalize_analysis(self, results: List[Dict[str, Any]]):
        """将结果持久化到数据库并更新角色档案"""
        for entry in results:
            custom_id = entry.get("custom_id", "")
            if not custom_id.startswith("chapter_"):
                continue
            
            chapter_idx = int(custom_id.split("_")[1])
            response = entry.get("response", {})
            body = response.get("body", {})
            choices = body.get("choices", [])
            
            if not choices:
                continue
            
            content_str = choices[0].get("message", {}).get("content", "")
            try:
                data = json.loads(content_str)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON for chapter {chapter_idx}")
                continue

            # 1. 更新数据库中的章节摘要/状态
            self.repository.update_analysis_result(
                self.session_id,
                chapter_idx,
                status=2,
                summary=data.get("summary"),
            )
            
            # 2. 检查状态变更并触发存档
            state_changes = data.get("state_changes", [])
            for change in state_changes:
                entity = change.get("entity")
                new_trait = change.get("new_trait")
                if entity and new_trait:
                    logger.info(f"🚨 识别到角色状态变更 [{chapter_idx}]: {entity} -> {new_trait}")
                    self.vector_store.add_character_trait(
                        name=entity,
                        trait={"appearance_update": new_trait, "reason": change.get("reason")},
                        chapter_idx=chapter_idx
                    )

            # 3. 同时保存常规角色特征（Map 阶段的产出）
            characters = data.get("characters", [])
            for char in characters:
                name = char.get("name")
                if name:
                    self.vector_store.add_character_trait(
                        name=name,
                        trait=char,
                        chapter_idx=chapter_idx
                    )

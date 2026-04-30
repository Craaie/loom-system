"""
Ingestion Service: 小说文本解析、双层分片及角色特征向量化。

职责对照: docs/loom_03_detailed_design.md §1.1
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

import aiofiles

from app.config.settings import settings
from app.db.repository import get_repository
from app.modules.vector_store import VectorStoreManager

logger = logging.getLogger("loom.ingestion")

# --- 常量 ---
MAX_TEXT_BYTES = 5 * 1024 * 1024  # 5 MB 内存保护阈值
CHAPTER_PATTERN = re.compile(
    r"(第[一二三四五六七八九十百千万零〇\d]+[章节回]|Chapter\s+\d+|^\d{1,4}[\.\s])",
    re.MULTILINE,
)
# NER 提取的 LLM Prompt 模板
CHARACTER_EXTRACTION_PROMPT = (
    "你是一个专业的小说分析助手。请从以下小说章节中提取所有角色的名称及其外貌、"
    "服装、性格描述。\n\n"
    "**输出要求**: 严格返回 JSON 格式，不要添加任何 markdown 标记。\n"
    "格式: {{\"角色名\": {{\"appearance\": \"外貌描述\", \"clothing\": \"服装描述\", "
    "\"personality\": \"性格描述\"}}}}\n"
    "如果章节中没有明确的角色描述，返回空对象 {{}}。\n\n"
    "--- 章节内容 ---\n{content}"
)


def decode_text_preview(content_bytes: bytes, max_chars: int = 4000) -> tuple[str, str]:
    """从文件头部字节中解码可读预览，并返回使用的编码。"""
    try:
        return content_bytes.decode("utf-8")[:max_chars], "utf-8"
    except UnicodeDecodeError:
        return content_bytes.decode("gbk", errors="ignore")[:max_chars], "gbk"


def read_text_preview(file_path: str, max_bytes: int = 8192, max_chars: int = 4000) -> tuple[str, str]:
    with open(file_path, "rb") as f:
        sample = f.read(max_bytes)
    return decode_text_preview(sample, max_chars=max_chars)


class IngestionService:
    """
    Ingestion Service 负责小说文本解析、双层分片及角色特征向量化。

    - 粗切层: 按章节自然分界拆分
    - 细切层: NER 提取角色并写入独立 Collection
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.session_id = session_id or "default_session"
        self.provider = provider or settings.DEFAULT_LLM_PROVIDER
        self.model_name = model_name or settings.DEFAULT_LLM_MODEL
        self.repository = get_repository()
        self.vector_store = VectorStoreManager(self.session_id, self.provider)

        # 初始化向量库目录 (按 session_id 隔离)
        self.persist_directory = os.path.join(
            settings.CHROMA_PERSIST_DIRECTORY, self.session_id
        )
        os.makedirs(self.persist_directory, exist_ok=True)

    # ------------------------------------------------------------------
    # 核心摄取层：流式切片与持久化 (Pragmatic Streamer)
    # ------------------------------------------------------------------

    async def stream_ingest(self, file_path: str, volume_id: str = None, encoding: str = "utf-8") -> int:
        """
        流式摄取小说文件，按章节切分并写入数据库。
        """
        logger.info(f"🚀 [任务-{self.session_id}] 开始流式摄取文件: {file_path}, Volume: {volume_id or 'N/A'}")
        
        current_chapter_index = 0
        current_chapter_title = "前言"
        current_chapter_content: List[str] = []
        
        async with aiofiles.open(file_path, mode='r', encoding=encoding, errors='ignore') as f:
            async for line in f:
                # 匹配章节标题
                match = CHAPTER_PATTERN.search(line)
                if match:
                    # 如果已有累积内容，保存当前章节
                    if current_chapter_content:
                        content_str = "".join(current_chapter_content).strip()
                        if content_str:
                            self.repository.save_chapter(
                                self.session_id, 
                                current_chapter_index, 
                                current_chapter_title, 
                                content_str,
                                volume_id=volume_id
                            )
                            current_chapter_index += 1
                    
                    # 开启新章节
                    current_chapter_title = line.strip()
                    current_chapter_content = []
                else:
                    current_chapter_content.append(line)
                    
            # 保存最后一个章节
            if current_chapter_content:
                content_str = "".join(current_chapter_content).strip()
                if content_str:
                    self.repository.save_chapter(
                        self.session_id, 
                        current_chapter_index, 
                        current_chapter_title, 
                        content_str,
                        volume_id=volume_id
                    )
                    current_chapter_index += 1

        logger.info(f"✅ 完成文件摄取: 共计 {current_chapter_index} 个章节记录在案。")
        return current_chapter_index

    async def ingest_content(self, content: str, volume_id: str = None) -> int:
        """
        针对直接输入的文本字符串进行内存切分（适用于 Snippet 或小型章节）。
        """
        logger.info(f"🚀 [任务-{self.session_id}] 开始直接切分文本内容，Volume: {volume_id or 'N/A'}")
        
        current_chapter_index = 0
        current_chapter_title = "前言"
        current_chapter_content = []
        
        lines = content.splitlines(keepends=True)
        for line in lines:
            match = CHAPTER_PATTERN.search(line)
            if match:
                if current_chapter_content:
                    content_str = "".join(current_chapter_content).strip()
                    if content_str:
                        self.repository.save_chapter(self.session_id, current_chapter_index, current_chapter_title, content_str, volume_id=volume_id)
                        current_chapter_index += 1
                current_chapter_title = line.strip()
                current_chapter_content = []
            else:
                current_chapter_content.append(line)
        
        if current_chapter_content:
            content_str = "".join(current_chapter_content).strip()
            if content_str:
                self.repository.save_chapter(self.session_id, current_chapter_index, current_chapter_title, content_str, volume_id=volume_id)
                current_chapter_index += 1
                
        return current_chapter_index

    # ------------------------------------------------------------------
    # 细切层：角色实体提取
    # ------------------------------------------------------------------

    async def build_character_archive(
        self,
        chapters: List[Dict[str, Any]],
        llm: Any,
        max_content_chars: int = 3000,
        analysis_prompt: str = ""
    ) -> Dict[str, Any]:
        """
        细切层：使用 LLM 提取角色特征并存入向量库。
        """
        character_registry: Dict[str, Any] = {}
        
        # 构造增强的提取 Prompt
        extraction_prompt = f"{CHARACTER_EXTRACTION_PROMPT}\n\n**User Custom Instructions**: {analysis_prompt}" if analysis_prompt else CHARACTER_EXTRACTION_PROMPT

        for chapter in chapters:
            content_slice = chapter["content"][:max_content_chars]
            prompt = extraction_prompt.format(content=content_slice)

            try:
                response = await llm.ainvoke(prompt)
                # 清洗可能的 markdown 标记
                raw = response.content.strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                chars = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Chapter {chapter['index']} ({chapter['title']}): "
                    f"JSON parse failed: {e}"
                )
                continue
            except Exception as e:
                logger.warning(
                    f"Chapter {chapter['index']} ({chapter['title']}): "
                    f"NER extraction failed: {e}"
                )
                continue

            from app.agents.visual.image_gen import ImageGenerator
            img_gen = ImageGenerator()

            # 合并到 registry（后出现的描述合并更新旧的）
            for name, desc in chars.items():
                if name in character_registry:
                    # 增量合并，不覆盖已有字段
                    existing = character_registry[name]
                    for k, v in desc.items():
                        if v and (k not in existing or not existing[k]):
                            existing[k] = v
                else:
                    character_registry[name] = desc

                # 角色跳脸防崩坏：为新角色生成圣经锚点参考图
                if "reference_image_url" not in character_registry[name]:
                    appearance = character_registry[name].get("appearance", "")
                    clothing = character_registry[name].get("clothing", "")
                    if appearance or clothing:
                        logger.info(f"🎨 为新增角色 '{name}' 固化圣经锚点参考图...")
                        try:
                            dummy_scene = {
                                "scene_index": f"char_{hash(name) % 10000}",
                                "image_prompt": f"Character concept art, portrait of single character. Appearance: {appearance}. Clothing: {clothing}. Full body or medium shot, clear facial features, solid white background.",
                                "visual_style": "High quality, highly detailed, character setup sheet"
                            }
                            # 伪造一个简单的 State 让生成器工作
                            dummy_state = {"thread_id": self.session_id, "asset_manifest": {}}
                            res = await img_gen._generate_single(dummy_scene, dummy_state)
                            if res.status == "done":
                                character_registry[name]["reference_image_url"] = res.image_path
                                logger.info(f"✅ 角色 '{name}' 参考图落地成功: {res.image_path}")
                        except Exception as e:
                            logger.error(f"❌ 角色 '{name}' 参考图生成失败: {e}")

                # 将描述写入该角色的独立 Collection
                try:
                    self.vector_store.add_character_trait(
                        name=name,
                        trait=desc,
                        chapter_idx=chapter["index"]
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to write character '{name}' to vector store: {e}"
                    )

        logger.info(
            f"Extracted {len(character_registry)} characters for session "
            f"{self.session_id}"
        )

        # 持久化 registry 到 JSON
        self.save_character_registry(character_registry)
        return character_registry


    # ------------------------------------------------------------------
    # 角色记忆持久化 (JSON)
    # ------------------------------------------------------------------

    def save_character_registry(self, registry: Dict[str, Any]) -> None:
        """将 character_registry 持久化到 JSON 文件"""
        path = os.path.join(self.persist_directory, "character_registry.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(registry, f, ensure_ascii=False, indent=2)
            logger.info(f"Character registry saved to {path}")
        except IOError as e:
            logger.error(f"Failed to save character registry: {e}")

    def load_character_registry(self) -> Optional[Dict[str, Any]]:
        """从 JSON 文件加载 character_registry（缓存命中时使用）"""
        path = os.path.join(self.persist_directory, "character_registry.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    registry = json.load(f)
                logger.info(
                    f"Loaded character registry from {path} "
                    f"({len(registry)} characters)"
                )
                return registry
            except (IOError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load character registry: {e}")
        return None

    # ------------------------------------------------------------------
    # 向量库访问
    # ------------------------------------------------------------------


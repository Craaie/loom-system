"""
Storyboard Agent: 将小说内容转化为结构化的分镜脚本 (Pydantic JSON)。

职责对照: docs/loom_03_detailed_design.md §1.2 & docs/implementation-plan-v1.md §4
输出保证: Pydantic 强校验 + Few-shot 示例 + 降级兜底模板
"""

import json
import logging
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field, ValidationError, AliasChoices
from langchain_core.prompts import ChatPromptTemplate

from app.core.state import LoomState
from app.config.settings import settings
from app.modules.cost_guard import update_and_check_cost
from app.modules.vector_store import VectorStoreManager
from app.core.utils import extract_json

logger = logging.getLogger("loom.storyboard")


class Scene(BaseModel):
    """单条分镜描述模型"""
    scene_index: int = Field(..., description="分镜序号")
    source_text: str = Field(..., description="对应的小说原文片段")
    image_prompt: str = Field(..., validation_alias=AliasChoices("image_prompt", "description"), description="分镜的视觉画面详细描述/生图提示词")
    characters: List[str] = Field(default_factory=list, description="本场出现的角色列表")
    visual_style: str = Field(..., description="视觉风格与灯光建议 (如：暖色调, 暗调, 逆光)")
    shot_scale: str = Field(default="Medium shot", description="电影摄影景别 (如: Extreme close-up, Close-up, Medium shot, Full shot, Long shot)")
    camera_angle: str = Field(default="Eye-level", description="机位视角 (如: Eye-level, High angle, Low angle, Over-the-shoulder, Aerial)")
    camera_movement: str = Field(default="Static", description="镜头运动方式 (如: Static, Pan, Tilt, Zoom in, Zoom out, Tracking)")
    narration: Optional[str] = Field(None, validation_alias=AliasChoices("narration", "dialogue"), description="本场配套的旁白或对话文本")
    background_music_hint: Optional[str] = Field(None, description="BGM 风格提示 (如：紧张, 舒缓)")
    duration_seconds: int = Field(default=5, ge=2, le=15, description="建议视频时长")
    importance: str = Field(default="medium", description="重要程度 (high/medium/low)")
    type: str = Field(default="normal", description="场景类型 (action/portrait/landscape/transition/normal)")
    physics_metadata: Optional[Dict[str, Any]] = Field(None, description="物理引擎生成的动态轨迹元数据")


class StoryboardOutput(BaseModel):
    """Agent 整体输出结构"""
    scenes: List[Scene] = Field(..., description="分镜列表")
    global_style: str = Field(..., description="全局视觉基调描述")


# 降级兜底模板 (3 轮自省失败后使用)
FALLBACK_TEMPLATE = StoryboardOutput(
    scenes=[
        Scene(
            scene_index=1,
            source_text="默认原文：系统自动生成的兜底描述",
            image_prompt="默认场景：基于原文的概括性画面描述",
            characters=[],
            visual_style="自然光 写实",
            shot_scale="Medium shot",
            camera_angle="Eye-level",
            camera_movement="Static",
            duration_seconds=5,
        )
    ],
    global_style="写实风格 自然色调",
)


FEW_SHOT_EXAMPLE = """
**示例输出** (请严格遵循此格式):
```json
{{
  "scenes": [
    {{
      "scene_index": 1,
      "source_text": "她第一次来到这个陌生的小镇",
      "image_prompt": "A young girl in a white Hanfu standing on an ancient stone bridge at sunset, hair blowing in the wind, backlit",
      "characters": ["林晓"],
      "visual_style": "Warm tones, backlit, ethereal",
      "shot_scale": "Wide shot",
      "camera_angle": "Eye-level",
      "camera_movement": "Slow zoom in",
      "narration": "她第一次来到这个陌生的小镇",
      "background_music_hint": "Gentle traditional Chinese music",
      "duration_seconds": 5,
      "importance": "high",
      "type": "landscape"
    }},
    {{
      "scene_index": 2,
      "source_text": "溪水清澈见底，倒映着她的身影",
      "image_prompt": "Close-up of clear stream water with the girl's reflection, camera tilting up to her face",
      "characters": ["林晓"],
      "visual_style": "Cool tones, hyper-realistic, volumetric light",
      "shot_scale": "Close-up",
      "camera_angle": "High angle",
      "camera_movement": "Vertical tilt up",
      "narration": null,
      "background_music_hint": "Quiet",
      "duration_seconds": 4,
      "importance": "medium",
      "type": "portrait"
    }}
  ],
  "global_style": "Traditional Chinese ink style, warm color palette"
}}
```"""


STORYBOARD_PROMPT = f"""你是一个专业的电影分镜师。
请根据提供的小说文本和角色档案，将其拆解为适合 AI 生成视频的分镜脚本。

**角色档案引用说明**:
在描述角色时，请务必严格参考档案中的外貌和服装特征，确保视觉一致性。
角色档案: {{character_registry}}

**任务目标**:
将以下文本拆解为连续的分镜，每个分镜应包含明确的视觉描述和对应的原文片段。
请确保为每个分镜生成以下内容：
1. `source_text`: **必须**直接引用小说中的原文片段（中文）。
2. `narration`: **必须**使用中文编写对应的旁白文本。
3. `image_prompt`: **必须**使用英文编写详细的视觉描述（以便 AI 绘图模型更好地理解环境与互动）。
4. `visual_style`: 使用英文描述光影氛围与色彩基调（如：Warm tones, moody lighting, HDR）。
5. 必须提供专业的摄影控制（使用英文结构化词汇）：`shot_scale` (电影景别，如 Close-up, Wide shot)，`camera_angle` (视角，如 Low angle, Top-down)，`camera_movement` (镜头运动，如 Static, Pan, Zoom in)。
请为每个分镜评估重要程度 (importance) 和类型 (type)：
- high: 视觉冲击大、动作多、开场或高潮
- action: 明显的人物动作或环境巨变

章节级摘要（用于理解长篇上下文）: {{story_context}}

当前原文片段 / 任务文本: {{novel_content}}

{FEW_SHOT_EXAMPLE}

**输出格式**:
必须严格按照上述 JSON 格式输出，不要添加任何多余文字。
"""


def _format_story_context(state: LoomState) -> str:
    """将章节摘要整理成适合注入 Prompt 的长文本上下文。"""
    global_context = state.get("global_context", {}) or {}
    chapter_summaries = global_context.get("chapter_summaries", []) or []
    if not chapter_summaries:
        return "无章节级摘要，可仅基于当前片段生成。"

    lines = []
    for idx, item in enumerate(chapter_summaries):
        title = item.get("title") or f"第{idx + 1}章"
        summary = item.get("summary") or ""
        if summary:
            lines.append(f"{idx + 1}. {title}: {summary}")
    return "\n".join(lines) if lines else "无章节级摘要，可仅基于当前片段生成。"


class StoryboardAgent:
    """
    分镜生成智能体：负责文本到结构化分镜的转化。
    支持 Pydantic 强校验 + 重试逻辑 + 降级兜底。
    """

    def __init__(self, model: Any) -> None:
        """
        Args:
            model: 已绑定的 LLM 实例 (需支持 structured_output 或手动处理)
        """
        self.model = model

    async def generate_storyboard(self, state: LoomState) -> Dict[str, Any]:
        """
        生成分镜主逻辑。集成 cost_guard 成本跟踪与 Temporal RAG。
        """
        novel_content = state.get("novel_content", "")
        session_id = state.get("session_id", "default_session")
        chapter_index = state.get("chapter_index", 0)  # 当前处理的章节序号
        
        # 1. 动态获取时序角色档案 (Temporal RAG)
        vsm = VectorStoreManager(session_id)
        character_registry = state.get("character_registry", {})
        contextual_registry = {}
        
        for name in character_registry.keys():
            profile = vsm.get_contextual_profile(name, chapter_index)
            if profile:
                contextual_registry[name] = profile
            else:
                # 兜底：如果向量库没搜到，用 registry 中的静态数据
                contextual_registry[name] = character_registry[name]

        # 2. 构造 Prompt
        analysis_prompt = state.get("analysis_prompt", "")
        story_context = _format_story_context(state)
        custom_hint = f"\n\n**User Custom Analysis Instructions**: {analysis_prompt}" if analysis_prompt else ""

        prompt = STORYBOARD_PROMPT.format(
            character_registry=json.dumps(contextual_registry, ensure_ascii=False),
            story_context=story_context,
            novel_content=novel_content,
        ) + custom_hint

        thread_id = state.get("thread_id", "unknown")
        logger.info(f"🎨 [任务-{thread_id}] 开始生成分镜脚本...")
        try:
            # 使用 LangChain 的结构化输出能力 (如果支持)
            if hasattr(self.model, "with_structured_output"):
                structured_llm = self.model.with_structured_output(StoryboardOutput)
                result = await structured_llm.ainvoke(prompt)
            else:
                # 兜底：手动调用并解析 JSON (针对部分提示性本地模型)
                response = await self.model.ainvoke(prompt)
                data = extract_json(response.content)
                result = StoryboardOutput.model_validate(data)

            logger.info(f"✅ [任务-{thread_id}] 成功生成 {len(result.scenes)} 个分镜场景。")

            # 成本跟踪 (估算值，生产环境应从 LLM response.usage 提取)
            estimated_cost = 0.01  # placeholder per-invoke cost
            try:
                cost_update = update_and_check_cost(state, estimated_cost)
            except Exception as cost_err:
                logger.warning(f"⚠️ [任务-{thread_id}] 成本检查失败，跳过: {cost_err}")
                cost_update = estimated_cost

            # 3. 物理引擎增强 (Physics Enrichment)
            from app.agents.visual.physics_engine import solve_physics
            enriched_scenes = []
            for scene in result.scenes:
                scene_dict = scene.model_dump()
                # 启发式识别需要物理计算的场景
                if scene.type == "action" or any(word in scene.image_prompt for word in ["跳", "落", "甩", "撞", "飞", "跃"]):
                    action_type = "fall" if any(w in (scene.image_prompt or "") for w in ["落", "坠"]) else "jump"
                    try:
                        physics_data = solve_physics(action_type, duration=scene.duration_seconds)
                        scene_dict["physics_metadata"] = physics_data
                        logger.info(f"✨ 已为分镜 {scene.scene_index} 注入物理轨迹 ({action_type})")
                    except Exception as pe:
                        logger.warning(f"⚠️ 物理计算失败: {pe}")
                enriched_scenes.append(scene_dict)

            # 返回需要累加到 State 的增量
            return {
                "storyboard_json": enriched_scenes,
                "approval_status": "storyboard_pending",  # 剧本生成后进入初审态
                "novel_content": "*** 阶段清洗：已释放冗余上下文内存 ***", # State 降噪，节省后续管线的庞大 Token 费用
                "error_count": 0,  # 成功则重置 (reduce_error_count: 0=reset)
                "cost_accumulator": cost_update,
            }

        except ValidationError as ve:
            logger.warning(f"⚠️ [任务-{thread_id}] 分镜 JSON 校验失败: {ve}")
            return {
                "error_count": 1,  # 累加 1
                "retry_history": [{"node": "storyboard", "error": str(ve), "type": "validation"}],
            }

        except Exception as e:
            logger.error(f"❌ [任务-{thread_id}] 分镜生成发生非预期错误: {e}", exc_info=True)

            # 不再在节点内部硬编码降级，而是将错误回传给 Supervisor
            # 让图层面决定是否切换模型 (AI 降级)
            return {
                "error_count": 1,
                "retry_history": [
                    {
                        "node": "storyboard",
                        "error": str(e),
                        "type": "runtime",
                        "ts": __import__("time").time()
                    }
                ],
            }

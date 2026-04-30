"""
Supervisor Module: 任务分类、路由决策与循环协调。

职责对照: docs/loom_03_detailed_design.md §1.2 & docs/implementation-plan-v1.md §4
路由规则:
  1. error_count >= 3 → Ollama 降级
  2. storyboard 已完成且 approved → video_gen
  3. text_length < 500 且无角色描写 → Ollama 本地
  4. else → 云端大模型 (Gemini/GPT)
  5. 成本 > 80% 阈值 → 预算告警并选择低成本模型
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, Union, Literal, Any

from pydantic import BaseModel, Field

from app.config.settings import settings
from app.core.state import LoomState, ApprovalStatus, GenerationMode

logger = logging.getLogger("loom.supervisor")


class RoutingDecision(BaseModel):
    """路由器决策结果"""
    next_node: str = Field(..., description="下一个要执行的节点名称")
    model_provider: Literal[
        "google", "openai", "ollama", "deepseek", "kling", 
        "wanx", "dashscope", "hailuo", "cogview", "flux", 
        "fish", "minimax_speech", "seedance", "mock"
    ] = Field(
        default="google", description="建议使用的模型提供商"
    )
    model_name: str = Field(..., description="具体的模型名称")
    reason: str = Field(..., description="路由决策的原因分析")


class SceneProductionStrategy(str, Enum):
    """单场景生产策略"""
    VIDEO_HIGH = "video_high"    # 高质量视频 (如 Kling)
    VIDEO_SIMPLE = "video_simple" # 简单视频 (如国产/本地)
    IMAGE_CINEMATIC = "image_cinematic" # 静态大图带镜头动效
    MOCK = "mock"


class SceneRouter:
    """
    场景智能路由器 ⭐：决定每个分镜是走视频管线还是图像管线。
    降本增效核心逻辑。
    """
    
    @staticmethod
    def route_scene(scene: Dict[str, Any]) -> SceneProductionStrategy:
        importance = scene.get("importance", "medium")
        scene_type = scene.get("type", "normal")
        duration = scene.get("duration_seconds", scene.get("duration", 5.0))
        
        # 1. 高能/高权重场景 -> Kling 3.0
        if importance == "high":
            return SceneProductionStrategy.VIDEO_HIGH
        
        # 2. 动作戏/大视觉冲击 -> 视频
        if scene_type in ["action", "visual_climax", "transition"]:
            return SceneProductionStrategy.VIDEO_HIGH
            
        # 3. 短镜头且非静态 -> 视频
        if duration <= 3.0 and importance != "low":
            return SceneProductionStrategy.VIDEO_SIMPLE
            
        # 4. 叙述、背景、对话 -> 静态图动效
        return SceneProductionStrategy.IMAGE_CINEMATIC


class TaskClassifier:
    """
    任务分类器：基于内容复杂度、角色信息、成本限额和当前阶段，决定后续路由。
    对照 loom_03_detailed_design.md §1.2 的三路路由 + 成本熔断。
    """

    @staticmethod
    def classify(state: LoomState) -> RoutingDecision:
        """
        核心分类逻辑：
        1. 错误率过高 → Ollama 降级
        2. 分镜已完成且已审批 → 路由到视频生成
        3. 成本预警 → 强制低成本模型
        4. 短文本 + 无角色描写 → 本地 Ollama
        5. 复杂场景 / 角色一致性 → 云端大模型
        """
        content = state.get("novel_content", "")
        char_registry = state.get("character_registry", {})
        storyboard = state.get("storyboard_json", [])
        cost_acc = state.get("cost_accumulator", 0.0)
        error_count = state.get("error_count", 0)
        approval_status = state.get("approval_status")
        cost_limit = float(state.get("cost_limit") or settings.MAX_COST_USD)

        is_low_budget = cost_acc > (cost_limit * 0.8)
        text_len = len(content)
        has_character_desc = bool(char_registry)

        # --- 路由决策树 ---

        # A. 严重错误处理：连续尝试均失败（包括 AI 降级尝试）
        if error_count >= 5:
            logger.error(
                "❌ [任务-%s] 严重错误：连续 %d 次生成失败，触发生命周期终点。",
                state.get("thread_id"), error_count
            )
            # 这里的决策将引导至 engine.py 中的终极静态兜底逻辑
            return RoutingDecision(
                next_node="END",
                model_provider="ollama",
                model_name="static-fallback",
                reason=f"Max retries ({error_count}) reached. Terminating with static fallback.",
            )

        # B. 错误率中等 → 触发第 1 级降级：切换至本地 Ollama (AI 降级)
        if error_count >= 3:
            logger.warning(
                "⚠️ [任务-%s] 错误率上升 (%d)，尝试切换至本地 Ollama 智能体进行降级生成。",
                state.get("thread_id"), error_count
            )
            return RoutingDecision(
                next_node="storyboard",
                model_provider="ollama",
                model_name=settings.OLLAMA_MODEL,
                reason="Cloud model failed 3 times, switching to local AI for degradation.",
            )

        # B. 分镜已完成 -> 检查后续素材 (图像 -> 音频)
        if storyboard:
            # 0. 剧本微操审查
            if str(approval_status) == str(ApprovalStatus.STORYBOARD_REJECTED.value):
                return RoutingDecision(
                    next_node="storyboard",
                    model_provider="openai",
                    model_name="gpt-4o",
                    reason="剧本被拒绝，即将执行重写",
                )

            # 1. 还需要关键帧？
            if not state.get("image_tasks"):
                return RoutingDecision(
                    next_node="image_gen",
                    model_provider=settings.IMAGE_PROVIDER if settings.IMAGE_PROVIDER else "wanx", # type: ignore
                    model_name=settings.IMAGE_MODEL if hasattr(settings, "IMAGE_MODEL") else "wanx-v1",
                    reason="分镜脚本已就绪，正在通过云端引擎并行生成高质量视觉关键帧。",
                )
            
            # 2. 还需要配音？
            if not state.get("audio_tasks"):
                return RoutingDecision(
                    next_node="tts_gen",
                    model_provider=settings.TTS_PROVIDER if settings.TTS_PROVIDER else "dashscope", # type: ignore
                    model_name="cosyvoice-v1",
                    reason="视觉素材已就绪，正在并行合成各场景的语音旁白音频。",
                )

            # 3. 素材全了，看审批状态
            if str(approval_status) == str(ApprovalStatus.APPROVED.value):
                return RoutingDecision(
                    next_node="video_gen",
                    model_provider="kling",
                    model_name="kling-3.0",
                    reason="所有素材（分镜/图片/音频）已获批准，进入视频生成阶段。",
                )
            
            return RoutingDecision(
                next_node="hitl_approval",
                model_provider=settings.DEFAULT_LLM_PROVIDER, # type: ignore
                model_name=settings.DEFAULT_LLM_MODEL,
                reason="分镜与素材已就绪，等待人工最终审核。",
            )

        # C. 成本预警：越过 80% 阈值时强制使用低成本模型
        if is_low_budget:
            logger.warning(
                "Cost %.4f exceeds 80%% of limit %.2f, routing to Ollama",
                cost_acc, cost_limit,
            )
            return RoutingDecision(
                next_node="storyboard",
                model_provider="ollama",
                model_name=settings.OLLAMA_MODEL,
                reason=f"Cost ${cost_acc:.4f} approaching limit, forcing local model.",
            )

        # D. 短文本 + 无角色描写 → 本地处理
        if text_len < 500 and not has_character_desc:
            return RoutingDecision(
                next_node="storyboard",
                model_provider="ollama",
                model_name=settings.OLLAMA_MODEL,
                reason="Low complexity (short text, no characters), routing to local Ollama.",
            )

        # E. 默认：复杂剧本分析 → 优先尊重用户在界面选择的模型 (batch_provider)
        provider = state.get("batch_provider", settings.DEFAULT_LLM_PROVIDER)
        model = state.get("batch_model", settings.DEFAULT_LLM_MODEL)

        return RoutingDecision(
            next_node="storyboard",
            model_provider=provider,  # type: ignore[arg-type]
            model_name=model,
            reason=f"Complex scenes required. Using {provider}/{model} based on initial choice.",
        )


def should_continue(state: LoomState) -> str:
    """
    LangGraph 条件路由函数：分镜节点后，决定是进入审批、重试还是结束。

    路由表:
      - error_count > 5 → __end__ (放弃)
      - approval_status == PENDING → hitl_approval (等待审批)
      - approval_status == REJECTED → storyboard (重新生成)
      - approval_status == APPROVED + 有分镜 → video_gen (视频生成)
      - novel_content 为空 → __end__
      - 其他 → supervisor (继续循环)
    """
    error_count = state.get("error_count", 0)
    approval_status = state.get("approval_status")
    storyboard = state.get("storyboard_json", [])

    # 1. 严重错误处理
    if error_count > 5:
        logger.error(
            "Max retries reached (%d) for thread %s, ending pipeline",
            error_count, state.get("thread_id"),
        )
        return "__end__"

    # 2. 依次检查阶段链路
    if not storyboard:
        return "storyboard"
    
    if str(approval_status) == str(ApprovalStatus.STORYBOARD_PENDING.value):
        return "hitl_storyboard"

    if str(approval_status) == str(ApprovalStatus.STORYBOARD_REJECTED.value):
        return "storyboard"

    if not state.get("image_tasks"):
        return "image_gen"
    
    if not state.get("audio_tasks"):
        return "tts_gen"

    if str(approval_status) == str(ApprovalStatus.PENDING.value):
        return "hitl_approval"

    if str(approval_status) == str(ApprovalStatus.REJECTED.value):
        return "storyboard" # 拒绝后重回起点

    if str(approval_status) == str(ApprovalStatus.APPROVED.value):
        return "video_gen"

    return "supervisor"

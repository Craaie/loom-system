from enum import Enum
from typing import Annotated, Dict, List, Optional, TypedDict, Any


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STORYBOARD_PENDING = "storyboard_pending"
    STORYBOARD_APPROVED = "storyboard_approved"
    STORYBOARD_REJECTED = "storyboard_rejected"


class GenerationMode(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"


class PipelineStage(str, Enum):
    """流水线阶段定义"""
    BATCH_ANALYSIS = "batch_analysis"
    SUPERVISOR = "supervisor"
    STORYBOARD = "storyboard"
    IMAGE_GEN = "image_gen"
    TTS_GEN = "tts_gen"
    HITL_APPROVAL = "hitl_approval"
    VIDEO_GEN = "video_gen"
    ASSEMBLY = "assembly"


# 阶段顺序定义（用于前端展示和重试逻辑）
PIPELINE_STAGE_ORDER = [
    PipelineStage.BATCH_ANALYSIS,
    PipelineStage.SUPERVISOR,
    PipelineStage.STORYBOARD,
    PipelineStage.IMAGE_GEN,
    PipelineStage.TTS_GEN,
    PipelineStage.HITL_APPROVAL,
    PipelineStage.VIDEO_GEN,
    PipelineStage.ASSEMBLY,
]


def reduce_cost(current: float, update: float) -> float:
    """累加成本的 reducer"""
    return current + update


def reduce_error_count(current: int, update: int) -> int:
    """错误计数 reducer：update=0 表示重置（成功时清零），update>0 表示累加"""
    if update == 0:
        return 0
    return current + update


def reduce_list(current: List[Any], update: List[Any]) -> List[Any]:
    """合并列表的 reducer（对含 task_id/id 的 dict 自动去重，以最新版本为准）"""
    merged = (current or []) + (update or [])
    seen: Dict[str, Any] = {}
    result: List[Any] = []
    for item in merged:
        if isinstance(item, dict):
            key = item.get("task_id") or item.get("id")
            if key:
                seen[key] = item  # 后出现的覆盖前面的
                continue
        result.append(item)
    return list(seen.values()) + result


def reduce_dict(current: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """合并字典的 reducer"""
    new_dict = (current or {}).copy()
    new_dict.update(update or {})
    return new_dict


class LoomState(TypedDict):
    """织影系统全局状态定义"""

    # === 核心标识 ===
    session_id: str  # 租户/任务唯一标识
    thread_id: str  # 线程标识
    chapter_index: int  # 当前处理章节索引（断点续跑锚点）

    # === 文本与记忆 ===
    novel_content: str  # 当前处理的文本原始片段
    analysis_prompt: str  # 用户提供的自定义分析指令
    global_context: Annotated[Dict[str, Any], reduce_dict]  # RAG 检索出的全局世界观/设定
    character_registry: Annotated[Dict[str, Any], reduce_dict]  # 已缓存的角色视觉档案

    # === 分镜产出 ===
    storyboard_json: Annotated[List[Dict[str, Any]], reduce_list]  # Pydantic 校验后的分镜数据

    # === HITL 控制 ===
    approval_status: str  # 枚举：PENDING / APPROVED / REJECTED
    approval_feedback: Optional[str]  # 用户修改意见

    # === 视频任务 ===
    # 存储 TaskRecord: {"task_id": str, "status": "pending/generating/done/failed", "path": str, "error": str}
    video_tasks: Annotated[List[Dict[str, Any]], reduce_list]

    # === 图像与音频任务 (Refinement) ===
    image_tasks: Annotated[List[Dict[str, Any]], reduce_list]
    audio_tasks: Annotated[List[Dict[str, Any]], reduce_list]

    # === 成本与韧性 ===
    cost_accumulator: Annotated[float, reduce_cost]  # 本次任务累计消耗 (USD)
    cost_limit: float  # 用户配置的成本上限 (触发熔断)
    error_count: Annotated[int, reduce_error_count]  # 错误计数器 (update=0 重置, >0 累加)
    retry_history: Annotated[List[Dict[str, Any]], reduce_list]  # 详细重试记录
    generation_mode: str  # 当前路由模式

    # === 执行追踪 (New in v3.0) ===
    # 存储执行日志：{"ts": float, "source": str, "level": str, "message": str}
    execution_logs: Annotated[List[Dict[str, Any]], reduce_list]
    # 场景级细粒度状态：{"scene_1": {"status": "done", "progress": 100}, ...}
    scene_metadata: Annotated[Dict[str, Any], reduce_dict]

    # === 路由决策传递 (Supervisor → Agent) ===
    _routing_model_provider: Optional[str]  # Supervisor 决策的模型提供商
    _routing_model_name: Optional[str]  # Supervisor 决策的模型名称
    _routing_next_node: Optional[str]  # Supervisor 决策的目标节点 (避免 router 重复计算)

    # === 资产清单 (v2.0 Asset Store) ===
    # key: hash(prompt+style), value: {"path": str, "type": "image/video", "ts": float}
    asset_manifest: Annotated[Dict[str, Any], reduce_dict]

    # === 批量分析 (DeepSeek Batch API & Parallel Fallback) ===
    batch_id: Optional[str]
    batch_status: str  # initial, submitted, completed, failed
    batch_provider: Optional[str]
    batch_model: Optional[str]

    # === Provider 覆盖配置 ===
    image_provider: Optional[str]
    tts_provider: Optional[str]
    video_provider: Optional[str]

    # === 流水线阶段追踪 (v3.1 Pipeline Tracking) ===
    # {"batch_analysis": {"status": "completed", "started_at": ..., "completed_at": ...}, ...}
    pipeline_status: Annotated[Dict[str, Any], reduce_dict]


def build_initial_pipeline_status() -> Dict[str, Any]:
    """构建初始流水线状态（所有阶段均为 pending）"""
    return {
        stage.value: {"status": "pending"}
        for stage in PipelineStage
    }

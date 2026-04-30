"""构建统一的 Loom 初始状态。"""

from __future__ import annotations

from typing import Optional

from app.config.settings import settings
from app.core.state import GenerationMode, build_initial_pipeline_status


def build_initial_loom_state(
    *,
    session_id: str,
    thread_id: str,
    novel_content: str = "",
    analysis_prompt: str = "",
    batch_provider: Optional[str] = None,
    batch_model: Optional[str] = None,
    image_provider: Optional[str] = None,
    tts_provider: Optional[str] = None,
    video_provider: Optional[str] = None,
    cost_limit: Optional[float] = None,
) -> dict:
    return {
        "session_id": session_id,
        "thread_id": thread_id,
        "chapter_index": 0,
        "novel_content": novel_content[:4000],
        "analysis_prompt": analysis_prompt or "",
        "global_context": {},
        "character_registry": {},
        "storyboard_json": [],
        "approval_status": "pending",
        "approval_feedback": None,
        "video_tasks": [],
        "image_tasks": [],
        "audio_tasks": [],
        "cost_accumulator": 0.0,
        "cost_limit": float(cost_limit if cost_limit is not None else settings.MAX_COST_USD),
        "error_count": 0,
        "retry_history": [],
        "generation_mode": GenerationMode.CLOUD.value,
        "execution_logs": [],
        "scene_metadata": {},
        "_routing_model_provider": None,
        "_routing_model_name": None,
        "_routing_next_node": None,
        "asset_manifest": {},
        "batch_id": None,
        "batch_status": "initial",
        "batch_provider": batch_provider,
        "batch_model": batch_model,
        "pipeline_status": build_initial_pipeline_status(),
        "image_provider": image_provider,
        "tts_provider": tts_provider,
        "video_provider": video_provider,
    }

"""Pipeline 流水线状态查询与从指定阶段重试的 API。"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.engine import get_app
from app.core.state import PipelineStage, PIPELINE_STAGE_ORDER, build_initial_pipeline_status
from app.services.engine_service import run_engine_task, active_threads, is_thread_active

logger = logging.getLogger("loom.router.pipeline")
router = APIRouter(prefix="/api/v2", tags=["pipeline"])


STAGE_LABEL_MAP = {
    "batch_analysis": "Content Analysis",
    "supervisor": "Routing Decision",
    "storyboard": "Storyboard Generation",
    "image_gen": "Image Generation",
    "tts_gen": "Voice Narration",
    "hitl_approval": "Human Review",
    "video_gen": "Video Generation",
    "assembly": "Final Assembly",
}


class RetryRequest(BaseModel):
    from_stage: Optional[str] = None  # 为 None 时自动检测第一个失败的阶段


@router.get("/jobs/{thread_id}/pipeline")
async def get_pipeline_status(thread_id: str):
    """
    查询指定任务的流水线阶段状态。
    返回按顺序排列的各阶段状态、时间信息和错误详情，
    前端用此数据渲染流水线进度条。
    """
    loom_app = await get_app()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = await loom_app.aget_state(config)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thread not found: {e}")

    ps = state.values.get("pipeline_status", {})
    is_active = is_thread_active(thread_id)

    stages = []
    for stage_enum in PIPELINE_STAGE_ORDER:
        stage_key = stage_enum.value
        info = ps.get(stage_key, {"status": "pending"})
        stages.append({
            "stage": stage_key,
            "label": STAGE_LABEL_MAP.get(stage_key, stage_key),
            **info,
        })

    # Derive overall status
    statuses = [s.get("status") for s in stages]
    if ps.get("assembly", {}).get("status") == "completed":
        overall = "completed"
        # 强制将所有被遗漏的中间等待节点（例如被由于重启漏掉更新状态的 hitl_approval）标记为已完成
        for stage_dict in stages:
            if stage_dict["status"] == "pending":
                stage_dict["status"] = "completed"
    elif "failed" in statuses:
        overall = "failed"
    elif "running" in statuses:
        overall = "running"
    elif all(s in ("completed", "skipped") for s in statuses):
        overall = "completed"
    else:
        overall = "in_progress" if any(s == "completed" for s in statuses) else "pending"

    return {
        "thread_id": thread_id,
        "overall_status": overall,
        "is_active": is_active,
        "stages": stages,
    }


@router.post("/jobs/{thread_id}/retry")
async def retry_from_stage(thread_id: str, req: RetryRequest):
    """
    从指定阶段重试失败/卡住的任务。
    
    工作原理：
    1. 若未指定 from_stage，自动检测第一个失败的阶段
    2. 将目标阶段及其后续所有阶段重置为 pending
    3. 通过 as_node 模拟前驱节点输出，让 LangGraph 重新调度目标节点
    4. 异步启动引擎从断点继续执行
    """
    # 智能检测：如果 thread_id 残留在 active_threads 中，但实际已无运行中的阶段，
    # 则说明是上次执行后未正确清理的僵尸记录，强制移除后允许重试。
    if thread_id in active_threads:
        try:
            loom_app_check = await get_app()
            config_check = {"configurable": {"thread_id": thread_id}}
            state_check = await loom_app_check.aget_state(config_check)
            ps_check = state_check.values.get("pipeline_status", {})
            has_running = any(
                info.get("status") == "running" 
                for info in ps_check.values() 
                if isinstance(info, dict)
            )
            if has_running:
                raise HTTPException(status_code=409, detail="Task is already running")
            else:
                logger.warning(f"⚠️ [重跑] thread {thread_id} 残留在 active_threads 中但无运行阶段，强制清理。")
                active_threads.discard(thread_id)
        except HTTPException:
            raise
        except Exception:
            # 状态读取失败时也强制清理，允许重试
            active_threads.discard(thread_id)

    loom_app = await get_app()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = await loom_app.aget_state(config)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thread not found: {e}")

    ps = state.values.get("pipeline_status", {})

    # Determine target stage
    target_stage = req.from_stage
    if not target_stage:
        # Auto-detect: find first failed stage
        for stage_enum in PIPELINE_STAGE_ORDER:
            info = ps.get(stage_enum.value, {})
            if info.get("status") == "failed":
                target_stage = stage_enum.value
                break

    if not target_stage:
        raise HTTPException(status_code=400, detail="No failed stage found. Specify from_stage explicitly.")

    # Validate stage name
    valid_stages = {s.value for s in PipelineStage}
    if target_stage not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage: {target_stage}. Valid: {valid_stages}")

    # Reset the target stage and all subsequent stages to pending
    reset_updates = {}
    found = False
    for stage_enum in PIPELINE_STAGE_ORDER:
        if stage_enum.value == target_stage:
            found = True
        if found:
            reset_updates[stage_enum.value] = {"status": "pending"}

    # 清除目标阶段及其下游的旧素材数据，确保重跑时不会因为旧数据而跳过生成
    stage_data_map = {
        "image_gen": "image_tasks",
        "tts_gen": "audio_tasks",
        "video_gen": "video_tasks",
    }
    data_reset = {}
    for stage_key in reset_updates:
        if stage_key in stage_data_map:
            data_reset[stage_data_map[stage_key]] = []
            logger.info(f"🧹 [重跑] 清除旧数据: {stage_data_map[stage_key]}")

    # 查找目标阶段的前驱节点，用于 as_node 模拟输出
    predecessor_node = None
    for i, stage_enum in enumerate(PIPELINE_STAGE_ORDER):
        if stage_enum.value == target_stage and i > 0:
            predecessor_node = PIPELINE_STAGE_ORDER[i-1].value
            break

    state_update = {"pipeline_status": reset_updates, "error_count": 0, **data_reset}

    if predecessor_node:
        await loom_app.aupdate_state(
            config,
            state_update,
            as_node=predecessor_node
        )
    else:
        # If it's the very first node
        await loom_app.aupdate_state(
            config,
            state_update,
        )

    logger.info(f"🔄 [重跑] thread {thread_id} 从阶段 [{target_stage}] 开始重新执行 (前驱节点: {predecessor_node})")
    asyncio.create_task(run_engine_task(None, config, thread_id))

    return {
        "status": "retrying",
        "thread_id": thread_id,
        "from_stage": target_stage,
        "reset_stages": list(reset_updates.keys()),
    }

"""任务管理路由：启动、查询、审批、恢复、SSE 推送"""

import os
import uuid
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Request
from sse_starlette.sse import EventSourceResponse

from app.schemas.job import JobCreate, ApprovalUpdate
from app.core.engine import get_app
from app.db.repository import get_repository
from app.services.engine_service import run_engine_task, event_manager, list_tracked_active_threads, is_thread_active
from app.services.state_factory import build_initial_loom_state
from app.agents.ingestion.processor import IngestionService, decode_text_preview

logger = logging.getLogger("loom.router.jobs")
router = APIRouter(prefix="/api/v2", tags=["jobs"])


async def _save_uploaded_file(file: UploadFile, novel_id: str) -> tuple[str, str, str]:
    """分块保存上传文件，并提取小体积文本预览。"""
    upload_dir = os.path.join("uploads", novel_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".txt"
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(upload_dir, safe_filename)

    preview_buffer = bytearray()
    with open(file_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            if len(preview_buffer) < 8192:
                preview_buffer.extend(chunk[: 8192 - len(preview_buffer)])
            f.write(chunk)

    preview_text, encoding = decode_text_preview(bytes(preview_buffer))
    return file_path, preview_text, encoding


@router.post("/jobs/upload")
async def upload_novel_file(
    file: UploadFile = File(...),
    novel_id: str = Form(...),
    volume_id: str = Form(None),
    provider: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    image_provider: Optional[str] = Form(None),
    tts_provider: Optional[str] = Form(None),
    video_provider: Optional[str] = Form(None),
    analysis_prompt: Optional[str] = Form(None),
    cost_limit: Optional[float] = Form(None),
):
    """上传 TXT 文件，流式入库章节后异步启动分析任务。"""
    repo = get_repository()
    file_path, preview_text, encoding = await _save_uploaded_file(file, novel_id)

    if volume_id:
        repo.update_volume_file_path(volume_id, file_path)
    else:
        repo.update_novel_file_path(novel_id, file_path)

    session_id = str(uuid.uuid4())
    thread_id = str(uuid.uuid4())

    ingester = IngestionService(session_id)
    await ingester.stream_ingest(file_path, volume_id=volume_id, encoding=encoding)

    initial_state = build_initial_loom_state(
        session_id=session_id,
        thread_id=thread_id,
        novel_content=preview_text,
        analysis_prompt=analysis_prompt or "",
        batch_provider=provider,
        batch_model=model,
        image_provider=image_provider,
        tts_provider=tts_provider,
        video_provider=video_provider,
        cost_limit=cost_limit,
    )
    config = {"configurable": {"thread_id": thread_id}}

    logger.info("💾 [任务-%s] 正在更新数据库最新任务 ID: novel=%s, volume=%s", thread_id, novel_id, volume_id)
    repo.update_novel_latest_thread(novel_id, thread_id)
    if volume_id:
        repo.update_volume_latest_thread(volume_id, thread_id)
    repo.upsert_thread_run(thread_id, session_id=session_id, status="queued")

    asyncio.create_task(run_engine_task(initial_state, config, thread_id))
    return {
        "thread_id": thread_id,
        "session_id": session_id,
        "filename": file.filename,
        "local_path": file_path,
    }


@router.post("/jobs/start")
async def start_job(job: JobCreate):
    """启动一个新的分镜任务。"""
    logger.info("➕ [任务-新建] 收到分镜任务请求")
    repo = get_repository()
    session_id = job.session_id or str(uuid.uuid4())
    thread_id = str(uuid.uuid4())

    content = job.novel_content or ""
    if content:
        ingester = IngestionService(session_id)
        await ingester.ingest_content(content, volume_id=job.volume_id)

    initial_state = build_initial_loom_state(
        session_id=session_id,
        thread_id=thread_id,
        novel_content=content,
        batch_provider=job.provider,
        batch_model=job.model,
        image_provider=job.image_provider,
        tts_provider=job.tts_provider,
        video_provider=job.video_provider,
        cost_limit=job.cost_limit,
    )

    config = {"configurable": {"thread_id": thread_id}}
    if job.volume_id:
        repo.update_volume_latest_thread(job.volume_id, thread_id)
    repo.upsert_thread_run(thread_id, session_id=session_id, status="queued")

    asyncio.create_task(run_engine_task(initial_state, config, thread_id))
    logger.info("📡 [任务-%s] 已在后台启动。", thread_id)
    return {"thread_id": thread_id, "session_id": session_id}


@router.get("/jobs/active")
async def list_active_jobs():
    """列出当前运行中的任务 ID。"""
    return {"active_threads": list_tracked_active_threads()}


@router.get("/jobs/{thread_id}/batch_status")
async def get_batch_progress(thread_id: str):
    """获取批量分析任务的实时处理进度。"""
    loom_app = await get_app()
    state = await loom_app.aget_state({"configurable": {"thread_id": thread_id}})
    batch_id = state.values.get("batch_id")

    if not batch_id:
        return {"progress": 100, "status": "completed", "total": 0, "completed": 0}

    from app.agents.ingestion.batch_analyzer import ParallelAnalyzer

    analyzer = ParallelAnalyzer(
        state.values.get("session_id", "default_session"),
        provider=state.values.get("batch_provider"),
        model=state.values.get("batch_model"),
    )
    try:
        status_data = await analyzer.get_batch_status(batch_id)
        counts = status_data.get("request_counts", {})
        total = counts.get("total", 0)
        completed = counts.get("completed", 0)
        progress = (completed / total * 100) if total > 0 else 0

        return {
            "progress": round(progress, 2),
            "status": status_data.get("status"),
            "total": total,
            "completed": completed,
        }
    except Exception as e:
        logger.error("Failed to fetch batch status: %s", e)
        return {"progress": 0, "status": "error", "error": str(e)}


@router.get("/jobs/{thread_id}/state")
async def get_job_state(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    loom_app = await get_app()
    state = await loom_app.aget_state(config)
    return {"thread_id": thread_id, "values": state.values, "next": state.next}


@router.post("/jobs/approve")
async def approve_job(update: ApprovalUpdate):
    """审批/恢复 HITL 拦截节点。"""
    config = {"configurable": {"thread_id": update.thread_id}}
    loom_app = await get_app()

    current_state = await loom_app.aget_state(config)
    current_next = current_state.next or ()

    if "hitl_storyboard" in current_next:
        as_node = "hitl_storyboard"
        status_value = "storyboard_approved" if update.status == "approved" else update.status
        logger.info("📋 [审批] 检测到 hitl_storyboard 拦截点，as_node=%s, status=%s", as_node, status_value)
    else:
        as_node = "hitl_approval"
        status_value = update.status
        logger.info("📋 [审批] 使用标准审批节点 as_node=%s, status=%s", as_node, status_value)

    await loom_app.aupdate_state(
        config,
        {"approval_status": status_value, "approval_feedback": update.feedback},
        as_node=as_node,
    )
    asyncio.create_task(run_engine_task(None, config, update.thread_id))
    return {"status": "resumed", "thread_id": update.thread_id}


@router.post("/jobs/{thread_id}/resume")
async def resume_job(thread_id: str):
    """手动触发恢复一个中断的任务。"""
    if is_thread_active(thread_id):
        return {"status": "already_running", "thread_id": thread_id}

    config = {"configurable": {"thread_id": thread_id}}
    asyncio.create_task(run_engine_task(None, config, thread_id))
    return {"status": "resumed", "thread_id": thread_id}


@router.get("/jobs/{thread_id}/stream")
async def stream_job_updates(request: Request, thread_id: str):
    """SSE 接口：流式推送 LangGraph 节点变化进度。"""

    async def event_generator():
        q = event_manager.get_queue(thread_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield msg
                    if msg["event"] in ["end", "error"]:
                        break
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
        finally:
            event_manager.remove_queue(thread_id, q)

    return EventSourceResponse(event_generator())

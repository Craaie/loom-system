"""卷次管理路由"""

import os
import uuid
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.schemas.novel import VolumeCreate
from app.db.repository import get_repository, VolumeModel
from app.services.engine_service import run_engine_task
from app.services.state_factory import build_initial_loom_state
from app.agents.ingestion.processor import IngestionService, read_text_preview

logger = logging.getLogger("loom.router.volumes")
router = APIRouter(prefix="/api/v2", tags=["volumes"])


@router.get("/novels/{novel_id}/volumes")
async def list_volumes(novel_id: str):
    repo = get_repository()
    volumes = repo.get_volumes(novel_id)
    return [
        {
            "id": v.id,
            "title": v.title,
            "index": v.index,
            "file_path": v.file_path,
            "latest_thread_id": v.latest_thread_id,
        }
        for v in volumes
    ]


@router.post("/volumes")
async def create_volume(req: VolumeCreate):
    repo = get_repository()
    volume_id = str(uuid.uuid4())
    volume = repo.create_volume(volume_id, req.novel_id, req.title, req.index)
    return {"id": volume.id, "title": volume.title}


@router.delete("/volumes/{id}")
async def delete_volume(id: str):
    repo = get_repository()
    success = repo.delete_volume(id)
    if not success:
        raise HTTPException(status_code=404, detail="Volume not found")
    return {"status": "deleted", "id": id}


@router.get("/volumes/{id}/file")
async def get_volume_file(id: str):
    repo = get_repository()
    db = repo.SessionLocal()
    try:
        volume = db.query(VolumeModel).filter(VolumeModel.id == id).first()
        if not volume or not volume.file_path:
            raise HTTPException(status_code=404, detail="File not found")

        path = volume.file_path
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Physical file missing")

        return FileResponse(path, filename=f"volume_{id}.txt")
    finally:
        db.close()


@router.post("/volumes/{id}/analyze")
async def start_existing_file_analysis(
    id: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    analysis_prompt: Optional[str] = None,
    image_provider: Optional[str] = None,
    tts_provider: Optional[str] = None,
    video_provider: Optional[str] = None,
    cost_limit: Optional[float] = None,
):
    """使用已存储的本地文件重新启动分析任务。"""
    repo = get_repository()
    db = repo.SessionLocal()
    try:
        volume = db.query(VolumeModel).filter(VolumeModel.id == id).first()
        if not volume or not volume.file_path:
            raise HTTPException(status_code=404, detail="Original file not found for this volume")
        if not os.path.exists(volume.file_path):
            raise HTTPException(status_code=404, detail="Physical file missing on server")

        existing_chapters = repo.get_chapters_by_volume(id)
        session_id = existing_chapters[0].session_id if existing_chapters else str(uuid.uuid4())
        thread_id = str(uuid.uuid4())

        preview_text, encoding = read_text_preview(volume.file_path)
        ingester = IngestionService(session_id)
        await ingester.stream_ingest(volume.file_path, volume_id=id, encoding=encoding)

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

        logger.info("💾 [任务-%s] 正在更新卷次 %s 的最新任务 ID", thread_id, id)
        repo.update_volume_latest_thread(id, thread_id)
        repo.upsert_thread_run(thread_id, session_id=session_id, status="queued")
        asyncio.create_task(run_engine_task(initial_state, config, thread_id))

        return {"thread_id": thread_id, "session_id": session_id}
    finally:
        db.close()

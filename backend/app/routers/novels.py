"""小说管理路由"""

import uuid
import logging

from fastapi import APIRouter, HTTPException

from app.schemas.novel import NovelCreate
from app.db.repository import get_repository

logger = logging.getLogger("loom.router.novels")
router = APIRouter(prefix="/api/v2", tags=["novels"])


@router.post("/novels")
async def create_novel(req: NovelCreate):
    """创建新小说记录，关联到指定项目"""
    repo = get_repository()
    novel_id = str(uuid.uuid4())
    novel = repo.create_novel(novel_id, req.project_id, req.title, req.author)
    return {"id": novel.id, "title": novel.title}


@router.get("/projects/{project_id}/novels")
async def list_novels(project_id: str):
    """获取指定项目下的所有小说列表"""
    repo = get_repository()
    novels = repo.get_novels(project_id)
    return [{"id": n.id, "title": n.title} for n in novels]


@router.get("/novels/{novel_id}")
async def get_novel(novel_id: str):
    """获取小说详情，包括最新的任务 thread_id（用于前端查看最近一次运行结果）"""
    repo = get_repository()
    novel = repo.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    return {
        "id": novel.id,
        "title": novel.title,
        "author": novel.author,
        "project_id": novel.project_id,
        "latest_thread_id": novel.latest_thread_id,
    }


@router.delete("/novels/{id}")
async def delete_novel(id: str):
    """删除指定小说记录"""
    repo = get_repository()
    success = repo.delete_novel(id)
    if not success:
        raise HTTPException(status_code=404, detail="Novel not found")
    return {"status": "deleted", "id": id}

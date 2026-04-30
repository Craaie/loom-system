"""线程管理路由：列表、删除、批量删除、状态更新"""

import sqlite3
import logging

from fastapi import APIRouter, HTTPException

from app.schemas.job import StateUpdate, BatchDeleteRequest, RegenerateRequest
from app.core.engine import get_app
from app.db.checkpointer import get_db_connection
from app.config.settings import settings
from app.services.cleanup_service import cleanup_thread_files, extract_session_id_from_checkpoint
from app.services.engine_service import regenerate_scene_asset, approve_and_continue

logger = logging.getLogger("loom.router.threads")
router = APIRouter(prefix="/api/v2", tags=["threads"])


@router.get("/threads")
async def list_threads():
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT thread_id FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 20"
            )
            threads = [row[0] for row in cursor.fetchall()]
        return {"threads": threads}
    except Exception as e:
        return {"threads": [], "error": str(e)}


@router.patch("/threads/{id}/state")
async def update_thread_state(id: str, req: StateUpdate):
    """手动覆盖或更新指定线程的状态（分镜、角色等）"""
    app_graph = await get_app()
    config = {"configurable": {"thread_id": id}}

    updates = {}
    if req.storyboard_json is not None:
        updates["storyboard_json"] = req.storyboard_json
    if req.character_registry is not None:
        updates["character_registry"] = req.character_registry
    if req.analysis_prompt is not None:
        updates["analysis_prompt"] = req.analysis_prompt
    if req.approval_status is not None:
        updates["approval_status"] = req.approval_status

    if not updates:
        return {"status": "no_changes"}

    try:
        await app_graph.aupdate_state(config, updates)
        logger.info(f"✅ [任务-{id}] 状态已手动更新: {list(updates.keys())}")
        return {"status": "success", "updated_fields": list(updates.keys())}
    except Exception as e:
        logger.error(f"❌ [任务-{id}] 状态更新失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update state: {str(e)}")


@router.post("/threads/{id}/scenes/{idx}/regenerate")
async def regenerate_scene(id: str, idx: int, req: RegenerateRequest):
    """单分镜独立重绘资产 (图片/音频)"""
    try:
        logger.info(f"🔄 [任务-{id}] 正在重新生成分镜 {idx} 的 {req.target}...")
        url = await regenerate_scene_asset(id, idx, req.target, req.new_prompt)
        logger.info(f"✅ [任务-{id}] 重新生成成功: {url}")
        return {"status": "success", "url": url}
    except ValueError as e:
        logger.error(f"❌ [任务-{id}] 重绘验证失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ [任务-{id}] 重绘发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/threads/{id}/approve")
async def approve_job(id: str):
    """人工审核通过：唤醒挂起的 Graph 执行后续生成"""
    try:
        logger.info(f"👍 [任务-{id}] 收到人工审核通过指令，正在唤醒流程...")
        await approve_and_continue(id)
        return {"status": "success"}
    except ValueError as e:
        logger.warning(f"⚠️ [任务-{id}] 唤醒失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ [任务-{id}] 唤醒发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.delete("/threads/{id}")
async def delete_thread(id: str):
    """彻底删除指定 thread_id 的所有状态数据 (LangGraph checkpointer + 物理文件)"""
    session_id = None
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT checkpoint FROM checkpoints WHERE thread_id = ? ORDER BY checkpoint_id DESC LIMIT 1",
                (id,),
            )
            row = cursor.fetchone()
            if row:
                session_id = extract_session_id_from_checkpoint(row[0])

            cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (id,))
            cursor.execute("DELETE FROM writes WHERE thread_id = ?", (id,))
            conn.commit()

        cleanup_thread_files(id, session_id)

        logger.info(f"🗑️ [任务-{id}] 状态与物理文件已彻底清理。")
        return {"status": "deleted", "thread_id": id}
    except Exception as e:
        logger.error(f"❌ 彻底删除线程 {id} 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/threads/batch-delete")
async def batch_delete_threads(req: BatchDeleteRequest):
    """批量删除任务状态与物理文件"""
    if not req.thread_ids:
        return {"status": "no_changes"}

    for tid in req.thread_ids:
        await delete_thread(tid)

    return {"status": "success", "count": len(req.thread_ids)}

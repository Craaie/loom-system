"""
Engine Service: 封装 LangGraph 引擎后台任务与 SSE 事件管理。
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List

from app.core.engine import get_app
from app.agents.visual.image_gen import ImageGenerator
from app.agents.audio.tts_gen import TTSGenerator
from app.db.repository import get_repository

logger = logging.getLogger("loom.engine_service")


class EventManager:
    """SSE 事件分发器。"""

    def __init__(self) -> None:
        self.queues: Dict[str, List[asyncio.Queue]] = {}

    def get_queue(self, thread_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.queues.setdefault(thread_id, []).append(q)
        return q

    async def publish(self, thread_id: str, event: str, data: Any) -> None:
        if thread_id in self.queues:
            for q in self.queues[thread_id]:
                await q.put({"event": event, "data": data})

    def remove_queue(self, thread_id: str, q: asyncio.Queue) -> None:
        if thread_id in self.queues:
            try:
                self.queues[thread_id].remove(q)
            except ValueError:
                pass
            if not self.queues[thread_id]:
                del self.queues[thread_id]


# --- 全局单例 ---
event_manager = EventManager()
active_threads: set[str] = set()


def list_tracked_active_threads() -> list[str]:
    """返回 DB 持久化状态与进程内状态合并后的活跃线程列表。"""
    repo = get_repository()
    return sorted(set(repo.list_active_thread_ids()) | set(active_threads))


def is_thread_active(thread_id: str) -> bool:
    """判断线程是否仍处于活跃执行态或待审批态。"""
    if thread_id in active_threads:
        return True
    repo = get_repository()
    record = repo.get_thread_run(thread_id)
    return bool(record and not record.is_finished and record.status in {"queued", "running", "waiting_approval"})


async def run_engine_task(
    initial_state: Optional[Dict],
    config: Dict,
    thread_id: str,
) -> None:
    """运行 LangGraph 引擎的核心后台任务。"""
    if thread_id in active_threads:
        logger.warning("任务 %s 已在运行中，跳出重复启动。", thread_id)
        return

    repo = get_repository()
    session_id = initial_state.get("session_id") if initial_state else None
    active_threads.add(thread_id)
    repo.upsert_thread_run(thread_id, session_id=session_id, status="running")
    logger.info("🚀 [任务-%s] 开始执行引擎流程...", thread_id)

    try:
        loom_app = await get_app()
        async for event in loom_app.astream(initial_state, config, stream_mode="values"):
            state = await loom_app.aget_state(config)
            current_node = state.next[0] if state.next else None
            repo.upsert_thread_run(
                thread_id,
                session_id=state.values.get("session_id"),
                status="running",
                current_node=current_node,
            )
            logger.info("✅ [任务-%s] 节点完成，当前待执行: %s", thread_id, state.next)
            await event_manager.publish(thread_id, "update", {
                "next": state.next,
                "cost": event.get("cost_accumulator", state.values.get("cost_accumulator", 0)),
                "last_node": current_node or "processing",
            })

        final_state = await loom_app.aget_state(config)
        waiting_for_approval = any(node in {"hitl_approval", "hitl_storyboard"} for node in (final_state.next or ()))
        final_status = "waiting_approval" if waiting_for_approval else "completed"
        repo.upsert_thread_run(
            thread_id,
            session_id=final_state.values.get("session_id"),
            status=final_status,
            current_node=(final_state.next[0] if final_state.next else None),
            finished=not waiting_for_approval,
        )
        logger.info("🏁 [任务-%s] 流程执行结束，状态=%s。", thread_id, final_status)
        await event_manager.publish(thread_id, "end", final_status)
    except Exception as e:
        logger.error("❌ [任务-%s] 引擎执行异常: %s", thread_id, e)
        repo.upsert_thread_run(thread_id, session_id=session_id, status="failed", error=str(e), finished=True)
        await event_manager.publish(thread_id, "error", str(e))
    finally:
        active_threads.discard(thread_id)


async def regenerate_scene_asset(thread_id: str, scene_index: int, target: str, new_prompt: Optional[str] = None) -> str:
    """局部资产热重绘：只重新生成指定分镜的单个资产。"""
    loom_app = await get_app()
    config = {"configurable": {"thread_id": thread_id}}

    state_snapshot = await loom_app.aget_state(config)
    if not state_snapshot or not state_snapshot.values:
        raise ValueError(f"State not found for thread_id {thread_id}")

    current_state = state_snapshot.values
    storyboards = current_state.get("storyboard_json", [])
    if not (0 <= scene_index < len(storyboards)):
        raise ValueError(f"Invalid scene_index {scene_index}")

    scene = storyboards[scene_index]
    scene_task_suffix = scene.get("scene_index", scene_index)

    if new_prompt:
        if target == "image":
            scene["image_prompt"] = new_prompt
        elif target == "audio":
            scene["narration"] = new_prompt

    asset_url = ""
    if target == "image":
        generator = ImageGenerator()
        res = await generator._generate_single(scene, current_state)
        asset_url = res.image_path
        tasks = current_state.get("image_tasks", [])
        for task in tasks:
            if task.get("task_id") == f"img_{scene_task_suffix}":
                task.update({
                    "image_path": res.image_path,
                    "local_path": res.local_path,
                    "status": "done",
                })
        current_state["image_tasks"] = tasks
    elif target == "audio":
        generator = TTSGenerator()
        res = await generator._generate_single(scene, thread_id)
        asset_url = res.audio_path
        tasks = current_state.get("audio_tasks", [])
        for task in tasks:
            if task.get("task_id") == f"audio_{scene_task_suffix}":
                task.update({
                    "audio_path": res.audio_path,
                    "local_path": res.local_path,
                    "status": "done",
                })
        current_state["audio_tasks"] = tasks
    else:
        raise ValueError(f"Invalid target: {target}")

    current_state["storyboard_json"] = storyboards
    await loom_app.aupdate_state(config, current_state)
    return asset_url


async def approve_and_continue(thread_id: str) -> None:
    """唤醒处于 HITL 拦截状态的 LangGraph 图。"""
    loom_app = await get_app()
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = await loom_app.aget_state(config)

    if not state_snapshot.next:
        raise ValueError(f"Task {thread_id} is not waiting or has already finished.")

    asyncio.create_task(run_engine_task(None, config, thread_id))

"""
Video Generation Module: 并发视频生成 + Semaphore 限流 + 超时保护。
"""

import asyncio
import logging
import os
from typing import Dict, Any, List

from aiolimiter import AsyncLimiter
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

from app.config.settings import settings
from app.core.state import LoomState
from app.modules.asset_paths import build_asset_urls, pick_local_path
from app.modules.cost_guard import update_and_check_cost
from app.modules.asset_store import generate_asset_hash, get_cached_asset, save_asset_to_cache
from app.providers.base import ProviderRegistry

logger = logging.getLogger("loom.video_gen")

_rate_limiter = AsyncLimiter(max_rate=10, time_period=60)


class VideoTaskResult(BaseModel):
    task_id: str = Field(..., description="任务唯一标识")
    status: str = Field(default="pending", description="pending/generating/done/failed")
    video_path: str = Field(default="", description="前端可访问的视频 URL")
    local_path: str = Field(default="", description="视频本地路径")
    error: str = Field(default="", description="错误信息 (如有)")
    provider: str = Field(default="kling", description="使用的生成服务商")
    asset_update: Dict[str, Any] = Field(default_factory=dict, exclude=True)


class VideoGenerator:
    """视频生成器：支持并发限流、超时保护和缓存复用。"""

    def __init__(self, provider_name: str = None) -> None:
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_VIDEO_TASKS)
        self.timeout = settings.VIDEO_API_TIMEOUT_SECONDS
        if not provider_name:
            provider_name = settings.VIDEO_PROVIDER
        self.provider = ProviderRegistry.get_video_provider(provider_name)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _invoke_provider(self, image_path: str, prompt: str, output_path: str):
        async with _rate_limiter:
            return await asyncio.wait_for(
                self.provider.image_to_video(
                    image_path=image_path,
                    prompt=prompt,
                    output_path=output_path,
                ),
                timeout=self.timeout,
            )

    async def _generate_single(self, scene: Dict[str, Any], state: LoomState) -> VideoTaskResult:
        prompt = scene.get("image_prompt", scene.get("description", ""))
        style = scene.get("visual_style", "")
        image_tasks = state.get("image_tasks", [])
        scene_idx = scene.get("scene_index", 0)
        task_id = f"video_{scene_idx}"
        source_image = ""
        for task in image_tasks:
            if task.get("task_id") == f"img_{scene_idx}":
                source_image = pick_local_path(task, "local_path", "image_path")
                break

        if not source_image:
            return VideoTaskResult(
                task_id=task_id,
                status="failed",
                error="Missing source image for video generation",
                provider=self.provider.name,
            )

        hash_key = generate_asset_hash(prompt, style, "video")
        cached = get_cached_asset(state, hash_key)
        if cached:
            urls = build_asset_urls(cached["path"])
            return VideoTaskResult(
                task_id=task_id,
                status="done",
                video_path=urls["public_url"],
                local_path=urls["local_path"],
                provider="cache",
            )

        async with self.semaphore:
            try:
                thread_id = state.get("thread_id", "mock")
                target_dir = os.path.join(".", "output", thread_id, "video")
                os.makedirs(target_dir, exist_ok=True)
                target_path = os.path.join(target_dir, f"video_{scene_idx}.mp4")
                result = await self._invoke_provider(source_image, prompt, target_path)
                if result.status == "done":
                    asset_update = save_asset_to_cache(state, hash_key, result.file_path, "video")
                    urls = build_asset_urls(result.file_path)
                    return VideoTaskResult(
                        task_id=task_id,
                        status="done",
                        video_path=urls["public_url"],
                        local_path=urls["local_path"],
                        provider=result.provider,
                        asset_update=asset_update,
                    )
                return VideoTaskResult(
                    task_id=task_id,
                    status="failed",
                    error=result.error,
                    provider=result.provider,
                )
            except asyncio.TimeoutError:
                logger.error("❌ [任务-%s] Provider %s 调用超时 (阈值: %ss)", task_id, self.provider.name, self.timeout)
                return VideoTaskResult(task_id=task_id, status="failed", error="Timeout", provider=self.provider.name)
            except Exception as e:
                logger.error("❌ [任务-%s] 生成时发生意外错误: %s", task_id, e, exc_info=True)
                return VideoTaskResult(task_id=task_id, status="failed", error=str(e), provider=self.provider.name)

    async def generate_batch(self, state: LoomState) -> Dict[str, Any]:
        scenes = state.get("storyboard_json", [])
        thread_id = state.get("thread_id", "unknown")
        if not scenes:
            logger.warning("⚠️ [任务-%s] 没有分镜数据，跳过视频生成。", thread_id)
            return {"video_tasks": []}

        logger.info("🎬 [任务-%s] 开始批量生成视频片段，共 %s 个分镜...", thread_id, len(scenes))
        results = await asyncio.gather(*(self._generate_single(scene, state) for scene in scenes), return_exceptions=True)

        video_tasks: List[Dict[str, Any]] = []
        all_asset_updates: Dict[str, Any] = {}
        failed_count = 0
        for result in results:
            if isinstance(result, VideoTaskResult):
                video_tasks.append(result.model_dump())
                if result.asset_update:
                    all_asset_updates.update(result.asset_update)
                if result.status == "failed":
                    failed_count += 1
            elif isinstance(result, Exception):
                video_tasks.append({
                    "task_id": "unknown",
                    "status": "failed",
                    "error": str(result),
                    "provider": "none",
                })
                failed_count += 1

        logger.info("✅ [任务-%s] 视频批量生成结束：成功 %s/%s", thread_id, len(scenes) - failed_count, len(scenes))

        success_count = sum(1 for task in video_tasks if task.get("status") == "done" and task.get("provider") != "cache")
        estimated_cost = success_count * 0.05
        cost_update = 0.0
        if estimated_cost > 0:
            cost_update = update_and_check_cost(state, estimated_cost)

        return {
            "video_tasks": video_tasks,
            "asset_manifest": all_asset_updates,
            "cost_accumulator": cost_update,
            "error_count": failed_count,
        }

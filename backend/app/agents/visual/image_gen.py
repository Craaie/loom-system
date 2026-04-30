"""
Image Generation Agent: 负责生成分镜关键帧，确保视觉一致性。
对接 OpenAI DALL-E 3 或本地 Flux 接口。
"""

import logging
import asyncio
from typing import Dict, Any

from pydantic import BaseModel, Field

from app.config.settings import settings
from app.core.state import LoomState
from app.modules.asset_paths import build_asset_urls, to_public_asset_url
from app.modules.asset_store import generate_asset_hash, get_cached_asset, save_asset_to_cache
from app.providers.base import ProviderRegistry

logger = logging.getLogger("loom.image_gen")


class ImageTaskResult(BaseModel):
    task_id: str
    status: str = "pending"
    image_path: str = ""
    local_path: str = ""
    error: str = ""
    provider: str = "openai"
    asset_update: Dict[str, Any] = Field(default_factory=dict, exclude=True)


MAX_CONCURRENT_IMAGES = 1


class ImageGenerator:
    """图像生成器：为每个分镜生成高质量关键帧。"""

    def __init__(self, provider_name: str = None):
        if not provider_name:
            provider_name = settings.IMAGE_PROVIDER
        self.provider = ProviderRegistry.get_image_provider(provider_name)

    async def _generate_single(self, scene: Dict[str, Any], state: LoomState) -> ImageTaskResult:
        """生成单张关键帧 (先查缓存)。"""
        thread_id = state.get("thread_id", "unknown")
        scene_idx = scene.get("scene_index", 0)
        task_id = f"img_{scene_idx}"

        prompt = scene.get("image_prompt", "")
        style = scene.get("visual_style", "")
        hash_key = generate_asset_hash(prompt, style, "image")

        cached = get_cached_asset(state, hash_key)
        if cached:
            urls = build_asset_urls(cached["path"])
            return ImageTaskResult(
                task_id=task_id,
                status="done",
                image_path=urls["public_url"],
                local_path=urls["local_path"],
                provider="cache",
            )

        ref_image_url = None
        characters = scene.get("characters", [])
        char_registry = state.get("character_registry", {})
        for char_name in characters:
            if char_name in char_registry and "reference_image_url" in char_registry[char_name]:
                ref_image_url = char_registry[char_name]["reference_image_url"]
                break

        prompt_full = f"Professional movie storyboard, {style}. {prompt}"
        logger.info("🎨 [任务-%s] 正在生成分镜 %s 的关键帧...", thread_id, scene_idx)

        try:
            target_path = f"./output/{thread_id}/img_{scene_idx}.jpg"
            kwargs = {
                "prompt": prompt_full,
                "style": style,
                "output_path": target_path,
            }
            if ref_image_url:
                kwargs["ref_image_url"] = ref_image_url
                logger.info("🔗 [任务-%s] 附加了角色圣经锚点图片: %s", thread_id, ref_image_url)

            result = await self.provider.generate(**kwargs)
            if result.status == "done":
                asset_update = save_asset_to_cache(state, hash_key, result.file_path, "image")
                urls = build_asset_urls(result.file_path)
                return ImageTaskResult(
                    task_id=task_id,
                    status="done",
                    image_path=urls["public_url"],
                    local_path=urls["local_path"],
                    provider=result.provider,
                    asset_update=asset_update,
                )
            return ImageTaskResult(
                task_id=task_id,
                status="failed",
                error=result.error,
                provider=result.provider,
            )
        except Exception as e:
            logger.error("❌ [任务-%s] 图像生成失败: %s", thread_id, e)
            return ImageTaskResult(task_id=task_id, status="failed", error=str(e))

    async def generate_batch(self, state: LoomState) -> Dict[str, Any]:
        """批量并行生成关键帧 (带 Provider 动态并发控制)。"""
        scenes = state.get("storyboard_json", [])
        thread_id = state.get("thread_id", "unknown")
        if not scenes:
            return {"image_tasks": []}

        concurrency_map = {
            "wanx": 1,
            "cogview": 2,
            "openai": 5,
            "flux": 3,
            "mock": 10,
        }
        limit = concurrency_map.get(self.provider.name, 1)
        semaphore = asyncio.Semaphore(limit)
        logger.info("🚦 [任务-%s] 使用并发度 %s 进行图像生成 (Provider: %s)", thread_id, limit, self.provider.name)

        async def sem_task(scene):
            async with semaphore:
                return await self._generate_single(scene, state)

        results = await asyncio.gather(*(sem_task(scene) for scene in scenes))
        estimated_cost = len(scenes) * 0.04

        all_asset_updates = {}
        for result in results:
            if result.asset_update:
                all_asset_updates.update(result.asset_update)

        return {
            "image_tasks": [result.model_dump() for result in results],
            "asset_manifest": all_asset_updates,
            "_node_cost": estimated_cost,
        }

"""
I2V (Image-to-Video) Agent: 基于关键帧图片生成动态视频片段。

接入模型: SVD (Stable Video Diffusion) / AnimateDiff / ComfyUI ControlNet
当前状态: 骨架模块，待接入真实 API。
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field

from app.config.settings import settings
from app.core.state import LoomState
from app.modules.asset_store import generate_asset_hash, get_cached_asset, save_asset_to_cache
from app.providers.base import ProviderRegistry

logger = logging.getLogger("loom.i2v")


class I2VTaskResult(BaseModel):
    """I2V 单任务结果"""
    task_id: str
    status: str = "pending"
    video_path: str = ""
    error: str = ""
    provider: str = "svd"
    source_image: str = ""
    asset_update: Dict[str, Any] = Field(default_factory=dict, exclude=True)


class I2VGenerator:
    """
    Image-to-Video 生成器：将静态关键帧转化为短视频。

    架构说明:
    - 接收 ImageGenerator 输出的关键帧路径
    - 调用 SVD / AnimateDiff / ComfyUI 进行动画化
    - 输出 2-5 秒的短视频片段
    - 集成 Asset Store 缓存

    与 FFmpeg Ken Burns 的区别:
    - Ken Burns: 纯几何变换 (缩放/平移)，无 AI 生成
    - I2V: AI 驱动的运动生成，可产生物体运动、表情变化等
    """

    def __init__(self, provider_name: str = None) -> None:
        self.timeout = getattr(settings, "I2V_API_TIMEOUT_SECONDS", 120)
        if not provider_name:
            provider_name = settings.VIDEO_PROVIDER
        self.provider = ProviderRegistry.get_video_provider(provider_name)

    async def _generate_single(
        self, image_path: str, scene: Dict[str, Any], state: LoomState
    ) -> I2VTaskResult:
        """基于单张关键帧生成短视频"""
        scene_idx = scene.get("scene_index", 0)
        task_id = f"i2v_{scene_idx}"
        prompt = scene.get("description", "")
        style = scene.get("visual_style", "")

        hash_key = generate_asset_hash(prompt, style, "i2v")

        # 1. 查缓存
        cached = get_cached_asset(state, hash_key)
        if cached:
            return I2VTaskResult(
                task_id=task_id,
                status="done",
                video_path=cached["path"],
                source_image=image_path,
                provider="cache",
            )

        logger.info(f"🎞️ [I2V-{scene_idx}] 正在将关键帧转化为视频: {image_path}")

        try:
            target_path = os.path.join(".", "output", "i2v", f"i2v_{scene_idx}.mp4")
            
            result = await self.provider.image_to_video(
                image_path=image_path,
                prompt=prompt,
                output_path=target_path
            )

            if result.status == "done":
                # 保存到缓存
                asset_update = save_asset_to_cache(state, hash_key, result.file_path, "i2v")
                
                # 转换为 Web URL
                video_url = result.file_path.replace("./output/", "/output/").replace("output/", "/output/")
                
                return I2VTaskResult(
                    task_id=task_id,
                    status="done",
                    video_path=video_url,
                    source_image=image_path,
                    provider=result.provider,
                    asset_update=asset_update,
                )
            else:
                return I2VTaskResult(
                    task_id=task_id,
                    status="failed",
                    error=result.error,
                    source_image=image_path,
                    provider=result.provider
                )

        except Exception as e:
            logger.error(f"❌ [I2V-{scene_idx}] 生成失败: {e}")
            return I2VTaskResult(
                task_id=task_id,
                status="failed",
                error=str(e),
                source_image=image_path,
            )

    async def generate_batch(
        self, scenes_to_convert: List[Dict[str, Any]], image_tasks: List[Dict[str, Any]], state: LoomState
    ) -> Dict[str, Any]:
        """批量 I2V 转化 (带并发控制)"""
        img_map = {t["task_id"]: t for t in image_tasks if t.get("status") == "done"}

        # 引入信号量限制并发
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_I2V)

        async def sem_task(img_path, scene):
            async with semaphore:
                return await self._generate_single(img_path, scene, state)

        tasks = []
        for scene in scenes_to_convert:
            idx = scene.get("scene_index", 0)
            img_key = f"img_{idx}"
            img_task = img_map.get(img_key)
            if img_task and img_task.get("image_path"):
                tasks.append(
                    sem_task(img_task["image_path"], scene)
                )

        if not tasks:
            return {"i2v_tasks": []}

        results = await asyncio.gather(*tasks, return_exceptions=True)

        i2v_tasks = []
        all_asset_updates = {}
        for r in results:
            if isinstance(r, I2VTaskResult):
                i2v_tasks.append(r.model_dump())
                if r.asset_update:
                    all_asset_updates.update(r.asset_update)
            elif isinstance(r, Exception):
                i2v_tasks.append({"task_id": "unknown", "status": "failed", "error": str(r)})

        return {
            "i2v_tasks": i2v_tasks,
            "asset_manifest": all_asset_updates,
        }

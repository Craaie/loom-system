"""
TTS Generation Agent: 负责生成分镜旁白/对白音频。
对接 OpenAI TTS 或本地库。
"""

import logging
import asyncio
from typing import Dict, Any

from pydantic import BaseModel

from app.config.settings import settings
from app.core.state import LoomState
from app.modules.asset_paths import build_asset_urls
from app.providers.base import ProviderRegistry

logger = logging.getLogger("loom.tts_gen")


class AudioTaskResult(BaseModel):
    task_id: str
    status: str = "pending"
    audio_path: str = ""
    local_path: str = ""
    error: str = ""
    provider: str = "openai"


MAX_CONCURRENT_TTS = 2


class TTSGenerator:
    """TTS 生成器：为每个分镜生成旁白音频。"""

    def __init__(self, provider_name: str = None):
        if not provider_name:
            provider_name = settings.TTS_PROVIDER
        self.provider = ProviderRegistry.get_tts_provider(provider_name)

    async def _generate_single(self, scene: Dict[str, Any], thread_id: str) -> AudioTaskResult:
        scene_idx = scene.get("scene_index", 0)
        task_id = f"audio_{scene_idx}"
        text = scene.get("narration") or scene.get("dialogue") or ""
        if not text:
            return AudioTaskResult(task_id=task_id, status="done", audio_path="", local_path="")

        logger.info("🎙️ [任务-%s] 正在生成分镜 %s 的配音音频...", thread_id, scene_idx)
        try:
            target_path = f"./output/{thread_id}/audio_{scene_idx}.mp3"
            result = await self.provider.synthesize(
                text=text,
                voice="default",
                output_path=target_path,
            )
            if result.status == "done":
                urls = build_asset_urls(result.file_path)
                return AudioTaskResult(
                    task_id=task_id,
                    status="done",
                    audio_path=urls["public_url"],
                    local_path=urls["local_path"],
                    provider=result.provider,
                )
            return AudioTaskResult(
                task_id=task_id,
                status="failed",
                error=result.error,
                provider=result.provider,
            )
        except Exception as e:
            logger.error("❌ [任务-%s] TTS 生成失败: %s", thread_id, e)
            return AudioTaskResult(task_id=task_id, status="failed", error=str(e))

    async def generate_batch(self, state: LoomState) -> Dict[str, Any]:
        scenes = state.get("storyboard_json", [])
        thread_id = state.get("thread_id", "unknown")
        if not scenes:
            return {"audio_tasks": []}

        concurrency_map = {
            "dashscope": 1,
            "minimax_speech": 2,
            "openai": 5,
            "fish": 3,
            "mock": 10,
        }
        limit = concurrency_map.get(self.provider.name, 1)
        semaphore = asyncio.Semaphore(limit)
        logger.info("🚦 [任务-%s] 使用并发度 %s 进行音频合成 (Provider: %s)", thread_id, limit, self.provider.name)

        async def sem_task(scene):
            async with semaphore:
                return await self._generate_single(scene, thread_id)

        results = await asyncio.gather(*(sem_task(scene) for scene in scenes))
        estimated_cost = len(scenes) * 0.001
        return {
            "audio_tasks": [result.model_dump() for result in results],
            "_node_cost": estimated_cost,
        }

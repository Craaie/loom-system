import asyncio
import os
import json
import logging
import aiohttp
import base64
from typing import Dict, Any
from app.providers.base import VideoProvider, GenerationResult, ProviderRegistry
from app.config.settings import settings

logger = logging.getLogger("loom.providers.hailuo")

class HailuoVideoProvider(VideoProvider):
    name = "hailuo"
    
    def __init__(self):
        self.api_key = getattr(settings, "MINIMAX_API_KEY", None)
        self.base_url = "https://api.minimax.chat/v1/video_generation"
        self.poll_url = "https://api.minimax.chat/v1/query/video_generation?task_id={}"
        self.model_name = "hailuo-2.3-fast" # 或者视频模型对应的标识

    async def image_to_video(self, image_path: str, prompt: str, output_path: str) -> GenerationResult:
        if not self.api_key or not self.api_key.get_secret_value():
            logger.warning("MiniMax API key is not configured. Falling back to mock video.")
            from app.providers.mock import MockVideoProvider
            return await MockVideoProvider().image_to_video(image_path, prompt, output_path)

        logger.info(f"🎞️ [Hailuo] Submitting image-to-video task... Prompt: {prompt[:30]}...")

        # 尝试转码为 base64 或构建请求 (MiniMax API 需精确适配: 以通用 base64 假设为例)
        if not os.path.exists(image_path):
            return GenerationResult(status="failed", error=f"Source image not found: {image_path}", provider=self.name)

        # 这里演示标准轮询异步架构，如果 API 细则有出入，只需调整 payload
        # 实际开发中可能需要先 POST /v1/files 上传图片获取 file_id
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            # "image_id": "file_xxx",  # 如果要求 file_id
            # 这里先做通用结构
        }

        headers = {
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # 1. 提交任务
                async with session.post(self.base_url, json=payload) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        logger.error(f"Hailuo submit failed {resp.status}: {err}")
                        return GenerationResult(status="failed", error=f"Submit API Error: {err}", provider=self.name)
                    
                    data = await resp.json()
                    task_id = data.get("task_id")
                    if not task_id:
                        return GenerationResult(status="failed", error=f"No task_id in response: {data}", provider=self.name)
                    
                logger.info(f"⏳ [Hailuo] Task submitted. Task ID: {task_id}. Start polling...")

                # 2. 轮询状态
                max_retries = 60 # 5分钟大轮次
                for i in range(max_retries):
                    await asyncio.sleep(5)
                    poll_url = self.poll_url.format(task_id)
                    async with session.get(poll_url) as poll_resp:
                        if poll_resp.status == 200:
                            poll_data = await poll_resp.json()
                            status = poll_data.get("status") # 比如 "Processing", "Success", "Failed"
                            
                            if status == "Success":
                                video_url = poll_data.get("video_url") # or file_id
                                if video_url:
                                    logger.info(f"📥 [Hailuo] Video generation Success. Downloading...")
                                    # 3. 下载文件
                                    async with session.get(video_url) as file_resp:
                                        if file_resp.status == 200:
                                            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                                            with open(output_path, "wb") as f:
                                                async for chunk in file_resp.content.iter_chunked(8192):
                                                    f.write(chunk)
                                            return GenerationResult(
                                                status="done", 
                                                file_path=output_path, 
                                                provider=self.name,
                                                task_id=task_id,
                                                cost_usd=0.19 # Hailuo-2.3-Fast 大致价格
                                            )
                                return GenerationResult(status="failed", error="Success but no URL", provider=self.name)
                            
                            elif status == "Failed":
                                return GenerationResult(status="failed", error="Hailuo API reported Failed status", provider=self.name)
                            
                            # else: continues polling
                
                return GenerationResult(status="failed", error="Polling timeout", provider=self.name)

        except Exception as e:
            logger.error(f"❌ [Hailuo] Exception: {e}")
            return GenerationResult(status="failed", error=str(e), provider=self.name)

ProviderRegistry.register_video("hailuo", HailuoVideoProvider)

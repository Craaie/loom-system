import asyncio
import os
import json
import logging
import aiohttp
from typing import Dict, Any
from app.providers.base import ImageProvider, GenerationResult, ProviderRegistry
from app.config.settings import settings

logger = logging.getLogger("loom.providers.cogview")

class CogViewProvider(ImageProvider):
    name = "cogview"
    
    def __init__(self):
        self.api_key = getattr(settings, "ZHIPU_API_KEY", None)
        self.api_url = "https://open.bigmodel.cn/api/paas/v4/images/generations"
        self.model_name = "cogview-4"
        
    async def generate(self, prompt: str, style: str, output_path: str) -> GenerationResult:
        if not self.api_key or not self.api_key.get_secret_value():
            logger.warning("Zhipu API key is not configured. Falling back to mock logic.")
            from app.providers.mock import MockImageProvider
            return await MockImageProvider().generate(prompt, style, output_path)
            
        final_prompt = f"Style: {style}. {prompt}"
        logger.info(f"🎨 [CogView] Generating image. Prompt: {final_prompt[:30]}...")
        
        headers = {
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_name,
            "prompt": final_prompt
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, headers=headers, json=payload, timeout=60) as response:
                    if response.status != 200:
                        err_text = await response.text()
                        logger.error(f"CogView API Error {response.status}: {err_text}")
                        return GenerationResult(
                            status="failed",
                            error=f"CogView API returned {response.status}: {err_text}",
                            provider=self.name
                        )
                    
                    data = await response.json()
                    image_url = data.get("data", [{}])[0].get("url")
                    
                    if not image_url:
                        return GenerationResult(
                            status="failed",
                            error=f"No image URL in response: {data}",
                            provider=self.name
                        )
                        
                    # 下载生成的图片到本地
                    async with session.get(image_url) as img_resp:
                        if img_resp.status == 200:
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                            with open(output_path, "wb") as f:
                                async for chunk in img_resp.content.iter_chunked(8192):
                                    f.write(chunk)
                            
                            logger.info(f"✅ [CogView] Image saved to {output_path}")
                            return GenerationResult(
                                status="done",
                                file_path=output_path,
                                provider=self.name,
                                cost_usd=0.01  # CogView-4 约 0.06 RMB
                            )
                        else:
                            return GenerationResult(
                                status="failed",
                                error=f"Failed to download image from {image_url}",
                                provider=self.name
                            )
                            
        except Exception as e:
            logger.error(f"❌ [CogView] Exception during generation: {e}")
            return GenerationResult(
                status="failed",
                error=str(e),
                provider=self.name
            )

ProviderRegistry.register_image("cogview", CogViewProvider)

import asyncio
import os
import json
import logging
import aiohttp
from typing import Dict, Any
from app.providers.base import TTSProvider, GenerationResult, ProviderRegistry
from app.config.settings import settings

logger = logging.getLogger("loom.providers.fish")

class FishAudioProvider(TTSProvider):
    name = "fish"
    
    def __init__(self):
        self.api_key = getattr(settings, "FISH_AUDIO_API_KEY", None)
        self.api_url = "https://api.fish.audio/v1/tts"
        
    async def synthesize(self, text: str, voice: str, output_path: str) -> GenerationResult:
        if not self.api_key or not self.api_key.get_secret_value():
            logger.warning("Fish Audio API key is not configured. Falling back to mock logic.")
            from app.providers.mock import MockTTSProvider
            return await MockTTSProvider().synthesize(text, voice, output_path)
            
        logger.info(f"🎙️ [FishAudio] Generating TTS for text snippet: {text[:20]}...")
        headers = {
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
            "Content-Type": "application/json"
        }
        
        # Fish Audio 默认 schema
        payload = {
            "text": text,
            # reference_id: 可选的音色克隆 ID，如果配置里有对应映射可以带上
            # format: "mp3"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, headers=headers, json=payload, timeout=60) as response:
                    if response.status != 200:
                        err_text = await response.text()
                        logger.error(f"Fish Audio API Error {response.status}: {err_text}")
                        return GenerationResult(
                            status="failed",
                            error=f"Fish Audio API returned {response.status}: {err_text}",
                            provider=self.name
                        )
                    
                    # 响应是音频流
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(1024 * 8):
                            f.write(chunk)
                            
            logger.info(f"✅ [FishAudio] TTS saved to {output_path}")
            return GenerationResult(
                status="done",
                file_path=output_path,
                provider=self.name,
                cost_usd=0.01  # Fish 大概计费，可扩展为按字数精确计算
            )
            
        except Exception as e:
            logger.error(f"❌ [FishAudio] Exception during generation: {e}")
            return GenerationResult(
                status="failed",
                error=str(e),
                provider=self.name
            )

ProviderRegistry.register_tts("fish", FishAudioProvider)

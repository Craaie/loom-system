import os
import json
import logging
import aiohttp
from typing import Dict, Any
from app.providers.base import TTSProvider, GenerationResult, ProviderRegistry
from app.config.settings import settings

logger = logging.getLogger("loom.providers.minimax_tts")

class MinimaxTTSProvider(TTSProvider):
    name = "minimax_speech"
    
    def __init__(self):
        self.api_key = getattr(settings, "MINIMAX_API_KEY", None)
        self.api_url = "https://api.minimax.chat/v1/t2a_v2"
        self.model_name = "speech-01-turbo" # 或者 speech-02
        
    async def synthesize(self, text: str, voice: str, output_path: str) -> GenerationResult:
        if not self.api_key or not self.api_key.get_secret_value():
            logger.warning("MiniMax API key is not configured. Falling back to mock logic.")
            from app.providers.mock import MockTTSProvider
            return await MockTTSProvider().synthesize(text, voice, output_path)
            
        logger.info(f"🎙️ [MiniMax-TTS] Generating speech for text: {text[:20]}...")
        headers = {
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
            "Content-Type": "application/json"
        }
        
        # 默认使用一个通用男声或者女声
        # 用户界面目前还没做细分选择，先给一个通用声线
        payload = {
            "model": self.model_name,
            "text": text,
            "stream": False,
            "audio_setting": {
                "voice_id": "male-qn-qingse" if voice in ["", "default"] else voice,
                "format": "mp3",
                "sample_rate": 32000
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, headers=headers, json=payload, timeout=60) as response:
                    if response.status != 200:
                        err_text = await response.text()
                        logger.error(f"MiniMax TTS API Error {response.status}: {err_text}")
                        return GenerationResult(
                            status="failed",
                            error=f"MiniMax API returned {response.status}: {err_text}",
                            provider=self.name
                        )
                    
                    # 响应是一个包含了 base64 或者是 hex 音频格式的 JSON
                    data = await response.json()
                    
                    if data.get("base_resp", {}).get("status_code") != 0:
                        return GenerationResult(
                            status="failed",
                            error=f"Fail from Minimax body: {data.get('base_resp')}",
                            provider=self.name
                        )
                    
                    # MiniMax v2 T2A json 返回的是一个 data 里面由 hex 的音频包组成
                    hex_data = data.get("data", {}).get("audio", "")
                    if hex_data:
                        audio_bytes = bytes.fromhex(hex_data)
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        with open(output_path, "wb") as f:
                            f.write(audio_bytes)
                    else:
                        return GenerationResult(status="failed", error="Empty audio hex string returned", provider=self.name)
                            
            logger.info(f"✅ [MiniMax-TTS] TTS saved to {output_path}")
            return GenerationResult(
                status="done",
                file_path=output_path,
                provider=self.name,
                cost_usd=0.002  # Placeholder 语音相对便宜
            )
            
        except Exception as e:
            logger.error(f"❌ [MiniMax-TTS] Exception during generation: {e}")
            return GenerationResult(
                status="failed",
                error=str(e),
                provider=self.name
            )

ProviderRegistry.register_tts("minimax_speech", MinimaxTTSProvider)

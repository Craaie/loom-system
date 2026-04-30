import os
import asyncio
import logging
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

from app.providers.base import TTSProvider, GenerationResult, ProviderRegistry
from app.config.settings import settings

logger = logging.getLogger("loom.providers.dashscope_tts")

class DashScopeTTSProvider(TTSProvider):
    name = "dashscope"
    
    def __init__(self):
        self.api_key = getattr(settings, "DASHSCOPE_API_KEY", None)
        
    async def synthesize(self, text: str, voice: str, output_path: str) -> GenerationResult:
        if not self.api_key or not self.api_key.get_secret_value():
            logger.warning("DashScope API key is not configured. Falling back to mock logic.")
            from app.providers.mock import MockTTSProvider
            return await MockTTSProvider().synthesize(text, voice, output_path)
            
        logger.info(f"🎙️ [Aliyun-TTS] Generating speech for text: {text[:20]}...")
        
        dashscope.api_key = self.api_key.get_secret_value()
        target_model = "cosyvoice-v1"
        
        try:
            # 使用 asyncio.to_thread 包装 dashscope 同步包以不阻塞主循环
            async def sync_synthesize_with_retry():
                max_tts_retries = 3
                for attempt in range(max_tts_retries):
                    try:
                        # 增加微小抖动，避免多个任务同时发起连接
                        await asyncio.sleep(attempt * 1.5) 
                        
                        def do_call():
                            # 默认选用阿里的龙小淳
                            synthesizer = SpeechSynthesizer(model=target_model, voice="longxiaochun")
                            return synthesizer.call(text)
                            
                        result = await asyncio.to_thread(do_call)
                        
                        # 检查返回结果类型与状态
                        if hasattr(result, "status_code") and result.status_code != 200:
                            err_msg = getattr(result, "message", "Unknown DashScope TTS error")
                            if "Throttling.RateQuota" in err_msg:
                                raise Exception(f"Throttling.RateQuota: {err_msg}")
                            raise Exception(f"DashScope Error ({result.status_code}): {err_msg}")
                            
                        # 获取二进制音频数据
                        if hasattr(result, "get_audio_data"):
                            return result.get_audio_data()
                        return result # 兼容旧版直接返回 bytes
                    except Exception as e:
                        if "Throttling.RateQuota" in str(e) or "websocket" in str(e).lower():
                            if attempt < max_tts_retries - 1:
                                wait_time = (attempt + 1) * 5 # 更激进的退避 (5s, 10s...)
                                logger.warning(f"⚠️ [Aliyun-TTS] Rate Limit. Retrying in {wait_time}s... ({attempt+1}/{max_tts_retries})")
                                await asyncio.sleep(wait_time)
                                continue
                        raise e
                
            audio_data = await sync_synthesize_with_retry()
            
            if not audio_data or len(audio_data) < 100: # 校验数据包大小，防止空文件
                throw_msg = f"DashScope TTS returned invalid/empty audio data (size: {len(audio_data) if audio_data else 0})"
                logger.error(f"❌ [Aliyun-TTS] {throw_msg}")
                return GenerationResult(status="failed", error=throw_msg, provider=self.name)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_data)
                
            logger.info(f"✅ [Aliyun-TTS] 音频保存成功: {output_path}")
            return GenerationResult(
                status="done",
                file_path=output_path,
                provider=self.name,
                cost_usd=0.001
            )
            
        except Exception as e:
            logger.error(f"❌ [Aliyun-TTS] Exception during generation: {e}")
            return GenerationResult(
                status="failed",
                error=str(e),
                provider=self.name
            )

# 注册引擎
ProviderRegistry.register_tts("dashscope", DashScopeTTSProvider)

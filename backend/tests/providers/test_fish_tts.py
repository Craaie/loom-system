import pytest
import os
from app.providers.tts.fish import FishAudioProvider
from app.config.settings import settings

@pytest.mark.asyncio
async def test_fish_tts_synthesis():
    """验证 Fish Audio 声音端点的连通性"""
    
    has_key = bool(settings.FISH_AUDIO_API_KEY and settings.FISH_AUDIO_API_KEY.get_secret_value())
    provider = FishAudioProvider()
    test_output_path = "./output/test_fish_audio.mp3"
    
    # 短请求节约成本
    resp = await provider.synthesize(
        text="你好，测试。",
        voice="default", # 这个看具体代码里允许的 voice
        output_path=test_output_path
    )
    
    if has_key:
        assert resp.status == "done", f"Fish TTS 调用失败: {resp.error}"
        assert resp.provider == "fish_tts"
        assert os.path.exists(test_output_path), "TTS 未能下载成功"
        
        # 扫尾清理
        os.remove(test_output_path)
    else:
        # 降级成 mock
        assert resp.status in ["done", "pending"], "Mock 无法放行 TTS"
        assert "mock" in resp.provider.lower()

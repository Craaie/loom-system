import pytest
import os
from app.providers.tts.minimax import MinimaxTTSProvider
from app.config.settings import settings

@pytest.mark.asyncio
async def test_minimax_tts_synthesis():
    """验证 MiniMax Speech-02 声音端点的连通性"""
    
    has_key = bool(settings.MINIMAX_API_KEY and settings.MINIMAX_API_KEY.get_secret_value())
    provider = MinimaxTTSProvider()
    test_output_path = "./output/test_minimax_audio.mp3"
    
    # 短请求节约成本
    resp = await provider.synthesize(
        text="你好，测试。",
        voice="male-qn-qingse", # 默认
        output_path=test_output_path
    )
    
    if has_key:
        assert resp.status == "done", f"MiniMax TTS 调用失败: {resp.error}"
        assert resp.provider == "minimax_speech"
        assert os.path.exists(test_output_path), "TTS 未能下载成功"
        
        # 扫尾清理
        os.remove(test_output_path)
    else:
        # 降级成 mock
        assert resp.status in ["done", "pending"], "Mock 无法放行 TTS"
        assert "mock" in resp.provider.lower()

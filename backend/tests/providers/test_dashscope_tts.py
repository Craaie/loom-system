import pytest
import os
from app.providers.tts.dashscope import DashScopeTTSProvider
from app.config.settings import settings

@pytest.mark.asyncio
async def test_dashscope_tts_synthesis():
    """验证通义 Dashscope TTS 声音端点的连通性"""
    
    has_key = bool(settings.DASHSCOPE_API_KEY and settings.DASHSCOPE_API_KEY.get_secret_value())
    provider = DashScopeTTSProvider()
    test_output_path = "./output/test_dashscope_audio.mp3"
    
    resp = await provider.synthesize(
        text="你好，阿里百炼测试。",
        voice="sambert-zhiwei-v1",
        output_path=test_output_path
    )
    
    if has_key:
        assert resp.status == "done", f"DashScope TTS 调用失败: {resp.error}"
        assert resp.provider == "dashscope"
        assert os.path.exists(test_output_path), "TTS 未能下载成功"
        os.remove(test_output_path)
    else:
        assert resp.status in ["done", "pending"], "Mock 无法放行 TTS"
        assert "mock" in resp.provider.lower()

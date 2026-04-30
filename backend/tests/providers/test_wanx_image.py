import pytest
import os
from app.providers.image.wanx import WanxImageProvider
from app.config.settings import settings

@pytest.mark.asyncio
async def test_wanx_generation():
    """验证阿里通义万相 Wanx 构图长串连通性"""
    
    has_key = bool(settings.DASHSCOPE_API_KEY and settings.DASHSCOPE_API_KEY.get_secret_value())
    provider = WanxImageProvider()
    test_output_path = "./output/test_wanx_output.png"
    
    # 向万相发送请求
    resp = await provider.generate(
        prompt="A very very simple cube.", # 极简生图验证
        style="Photography",
        output_path=test_output_path
    )
    
    if has_key:
        assert resp.status == "done", f"万相调用失败: {resp.error}"
        assert resp.provider == "wanx"
        assert os.path.exists(test_output_path), "万相未能下载生成图像"
        os.remove(test_output_path)
    else:
        assert "mock" in resp.provider.lower(), "没配 Key 时没有正确 fallback 到 mock"
        assert resp.status == "done"

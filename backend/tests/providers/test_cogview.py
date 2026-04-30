import pytest
import os
from unittest.mock import patch
from app.providers.image.cogview import CogViewProvider
from app.config.settings import settings

@pytest.mark.asyncio
async def test_cogview_generation():
    """验证智谱 CogView-4 图像生成的连通性"""
    
    # 鉴别当前环境是否有可用 Key
    has_key = bool(settings.ZHIPU_API_KEY and settings.ZHIPU_API_KEY.get_secret_value())
    
    provider = CogViewProvider()
    test_output_path = "./output/test_cogview_output.jpg"
    
    # 执行生成
    resp = await provider.generate(
        prompt="A very simple red apple on a white table.",
        style="Photography",
        output_path=test_output_path
    )
    
    if has_key:
        # 处于实名调用状态，断言应当得到真实的响应，并生成了图片
        assert resp.status == "done", f"真实 Key 调用失败: {resp.error}"
        assert resp.provider == "cogview"
        assert os.path.exists(test_output_path), "并未发现下载成功的图片文件"
        
        # 扫尾清理
        os.remove(test_output_path)
    else:
        # Mock 状态下的验证
        assert resp.provider == "mock_image", "没配 Key 时没有正确 fallback 到 mock 引擎"
        assert resp.status == "done"

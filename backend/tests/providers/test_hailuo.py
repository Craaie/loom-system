import pytest
import os
from unittest.mock import patch
from app.providers.video.hailuo import HailuoVideoProvider
from app.config.settings import settings

@pytest.mark.asyncio
async def test_hailuo_video_connectivity():
    """验证海螺视频大模型的 API 队列连通性 (短频不长时间轮询)"""
    
    has_key = bool(settings.MINIMAX_API_KEY and settings.MINIMAX_API_KEY.get_secret_value())
    provider = HailuoVideoProvider()
    test_output_path = "./output/test_hailuo_output.mp4"
    dummy_image = "./output/dummy_source.jpg"
    
    # 由于该测试会造成实际数分钟轮询并高额扣费，这里我们设计使用故意发无效文件测试官方拦截结构
    # 或者用极短轮询
    if has_key:
        # 准备一张假图来触发报错，以证明通道是通的并且网络回包结构能防挂
        with open(dummy_image, "w") as f:
            f.write("not a real image")
            
        resp = await provider.image_to_video(
            image_path=dummy_image,
            prompt="Make it move",
            output_path=test_output_path
        )
        
        # 海螺如果是假图或者格式不对，应该会在提交阶段直接抛错或者响应解析出不通过，不再瞎轮询
        assert resp.status == "failed", "应在校验步骤报错挡住乱调费用的假图"
        assert "mock" not in resp.provider.lower(), "有Key不应该走到 mock"
        
        os.remove(dummy_image)
    else:
        # Mock 下的校验
        resp = await provider.image_to_video(
            image_path="none",
            prompt="Test",
            output_path=test_output_path
        )
        assert "mock" in resp.provider.lower()
        assert resp.status == "done"

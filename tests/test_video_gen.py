import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.video.generator import VideoGenerator
from app.providers.base import GenerationResult


@pytest.mark.asyncio
async def test_video_gen_uses_local_image_and_normalizes_urls():
    provider = MagicMock()
    provider.name = "mock"
    provider.image_to_video = AsyncMock(return_value=GenerationResult(
        status="done",
        file_path="./output/test-thread/video/video_1.mp4",
        provider="mock",
    ))

    with patch("app.agents.video.generator.ProviderRegistry.get_video_provider", return_value=provider), \
         patch("app.agents.video.generator.get_cached_asset", return_value=None), \
         patch("app.agents.video.generator.save_asset_to_cache", return_value={}):
        generator = VideoGenerator("mock")
        state = {
            "thread_id": "test-thread",
            "storyboard_json": [{"scene_index": 1, "image_prompt": "Prompt", "visual_style": "Style"}],
            "image_tasks": [{
                "task_id": "img_1",
                "status": "done",
                "local_path": "./output/test-thread/img_1.jpg",
                "image_path": "/output/test-thread/img_1.jpg",
            }],
            "asset_manifest": {},
            "cost_accumulator": 0.0,
            "cost_limit": 10.0,
        }

        result = await generator.generate_batch(state)

    task = result["video_tasks"][0]
    assert task["status"] == "done"
    assert task["local_path"] == "./output/test-thread/video/video_1.mp4"
    assert task["video_path"] == "/output/test-thread/video/video_1.mp4"
    provider.image_to_video.assert_awaited_once()

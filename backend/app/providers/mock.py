import asyncio
import os
import logging
from app.providers.base import (
    ImageProvider, 
    TTSProvider, 
    VideoProvider, 
    GenerationResult,
    ProviderRegistry
)
from app.config.settings import settings
from app.modules.asset_store import save_asset_to_cache

logger = logging.getLogger("loom.providers.mock")

class MockImageProvider(ImageProvider):
    name = "mock"

    async def generate(self, prompt: str, style: str, output_path: str) -> GenerationResult:
        logger.info(f"🎨 [Mock] Generating image to {output_path}")
        await asyncio.sleep(1)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = f"ffmpeg -f lavfi -i \"color=c=royalblue:s=640x480:d=1\" -vframes 1 -y '{output_path}'"
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        return GenerationResult(
            status="done",
            file_path=output_path,
            provider="mock_image"
        )

class MockTTSProvider(TTSProvider):
    name = "mock"

    async def synthesize(self, text: str, voice: str, output_path: str) -> GenerationResult:
        logger.info(f"🎙️ [Mock] Generating audio to {output_path}")
        await asyncio.sleep(0.5)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = f"ffmpeg -f lavfi -i 'anullsrc=r=44100:cl=stereo' -t 2 -c:a libmp3lame -y '{output_path}'"
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        return GenerationResult(
            status="done",
            file_path=output_path,
            provider="mock_tts"
        )

class MockVideoProvider(VideoProvider):
    name = "mock"

    async def image_to_video(self, image_path: str, prompt: str, output_path: str) -> GenerationResult:
        logger.info(f"🎞️ [Mock] Generating video to {output_path} from {image_path}")
        await asyncio.sleep(1)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = f"ffmpeg -f lavfi -i \"color=c=darkorange:s=640x480:d=2\" -c:v libx264 -pix_fmt yuv420p -y '{output_path}'"
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        return GenerationResult(
            status="done",
            file_path=output_path,
            provider="mock_video"
        )

# Register automatically upon import
ProviderRegistry.register_image("mock", MockImageProvider)
ProviderRegistry.register_tts("mock", MockTTSProvider)
ProviderRegistry.register_video("mock", MockVideoProvider)

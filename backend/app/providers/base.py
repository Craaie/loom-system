import logging
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Optional, Dict, Type

logger = logging.getLogger("loom.providers")

class GenerationResult(BaseModel):
    """标准化的底层生成结果"""
    status: str            # "done" | "failed" | "pending"
    file_path: str = ""    # 生成的本地路径或可访问的 URL
    error: str = ""
    cost_usd: float = 0.0  # 本次调用的费用计算
    provider: str = ""     # 记录是由谁生成的 (例如 "hailuo-2.3-fast")
    task_id: str = ""      # 透传的关联任务 ID
    
    # 额外元数据（如耗时、特定的平台响应ID等），供后期排障使用
    metadata: Dict[str, str] = Field(default_factory=dict)


class ImageProvider(ABC):
    name: str = "base_image"
    
    @abstractmethod
    async def generate(self, prompt: str, style: str, output_path: str) -> GenerationResult:
        """
        生成关键帧。
        :param prompt: 画面描述
        :param style: 视觉风格描述
        :param output_path: 建议的文件保存路径
        """
        pass


class TTSProvider(ABC):
    name: str = "base_tts"
    
    @abstractmethod
    async def synthesize(self, text: str, voice: str, output_path: str) -> GenerationResult:
        """
        合成有声旁白。
        :param text: 旁白文本
        :param voice: 声音特征或音色 ID
        :param output_path: 建议的文件保存路径
        """
        pass


class VideoProvider(ABC):
    name: str = "base_video"
    
    @abstractmethod
    async def image_to_video(self, image_path: str, prompt: str, output_path: str) -> GenerationResult:
        """
        基于关键帧生成动态视频。
        :param image_path: 本地源关键帧路径或 URL
        :param prompt: 画面运动提示词
        :param output_path: 建议的文件保存路径
        """
        pass


class ProviderRegistry:
    """全局模型供应商注册中心"""
    
    _image_providers: Dict[str, Type[ImageProvider]] = {}
    _tts_providers: Dict[str, Type[TTSProvider]] = {}
    _video_providers: Dict[str, Type[VideoProvider]] = {}

    @classmethod
    def register_image(cls, name: str, provider_class: Type[ImageProvider]):
        cls._image_providers[name] = provider_class

    @classmethod
    def register_tts(cls, name: str, provider_class: Type[TTSProvider]):
        cls._tts_providers[name] = provider_class

    @classmethod
    def register_video(cls, name: str, provider_class: Type[VideoProvider]):
        cls._video_providers[name] = provider_class

    @classmethod
    def get_image_provider(cls, name: str) -> ImageProvider:
        if name not in cls._image_providers:
            raise ValueError(f"Unsupported image provider: {name}. Available: {list(cls._image_providers.keys())}")
        return cls._image_providers[name]()

    @classmethod
    def get_tts_provider(cls, name: str) -> TTSProvider:
        if name not in cls._tts_providers:
            raise ValueError(f"Unsupported TTS provider: {name}. Available: {list(cls._tts_providers.keys())}")
        return cls._tts_providers[name]()

    @classmethod
    def get_video_provider(cls, name: str) -> VideoProvider:
        if name not in cls._video_providers:
            raise ValueError(f"Unsupported video provider: {name}. Available: {list(cls._video_providers.keys())}")
        return cls._video_providers[name]()

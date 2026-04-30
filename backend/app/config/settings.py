"""系统全局配置管理 (Pydantic Settings)"""

from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    织影系统全局配置。
    所有 API Key 使用 SecretStr 保护，防止日志和序列化中泄露。
    """

    # API Keys (SecretStr 防泄露)
    GOOGLE_API_KEY: Optional[SecretStr] = None
    OPENAI_API_KEY: Optional[SecretStr] = None
    KLING_ACCESS_KEY: Optional[SecretStr] = None
    KLING_SECRET_KEY: Optional[SecretStr] = None
    DEEPSEEK_API_KEY: Optional[SecretStr] = None

    # LangSmith Tracing
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: Optional[SecretStr] = None
    LANGCHAIN_PROJECT: str = "loom-system"

    # Database & Storage
    DATABASE_URL: str = "sqlite:///./loom_state.db"
    CHROMA_PERSIST_DIRECTORY: str = "./db/chroma"

    # Cost Control
    MAX_COST_USD: float = 10.0

    # HITL Timeouts
    HITL_TIMEOUT_HOURS: int = 24
    HITL_AUTO_APPROVE_LOW_RISK: bool = True

    # Concurrency & Rate Limiting
    MAX_CONCURRENT_VIDEO_TASKS: int = 5
    VIDEO_API_TIMEOUT_SECONDS: int = 300
    ENABLE_MOCK_VIDEO: bool = True

    # Model Routing Default
    DEFAULT_LLM_PROVIDER: str = "google"  # google / openai / ollama
    DEFAULT_LLM_MODEL: str = "gemini-2.5-flash"

    # === 多供应商路由开关 ===
    IMAGE_PROVIDER: str = "wanx"       # cogview | wanx | flux | mock
    TTS_PROVIDER: str = "dashscope"    # fish | minimax_speech | dashscope | mock
    VIDEO_PROVIDER: str = "mock"       # hailuo | seedance | kling | mock

    # 各家 API Keys (SecretStr)
    ZHIPU_API_KEY: Optional[SecretStr] = None       # for CogView-4
    DASHSCOPE_API_KEY: Optional[SecretStr] = None   # for Wanx 2.5 & Qwen
    MINIMAX_API_KEY: Optional[SecretStr] = None     # for Speech-02 & Hailuo
    FISH_AUDIO_API_KEY: Optional[SecretStr] = None  # for Fish TTS
    # (Seedance 和可灵等 API Key 之前已定义或暂未明确环境变量名，可共用或新加)
    # KLING 已经有了，SEEDANCE 新加
    SEEDANCE_API_KEY: Optional[SecretStr] = None

    # Local Model (Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:4b"

    # Server
    API_PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )


# 单例配置对象
settings = Settings()

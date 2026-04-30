from pydantic import BaseModel
from typing import Optional

class AISettings(BaseModel):
    # Default Providers
    default_llm_provider: str = "google"
    default_llm_model: str = "gemini-2.0-flash"
    image_provider: str = "wanx"
    tts_provider: str = "dashscope"
    video_provider: str = "hailuo"
    
    # Secure Architecture Enforcement:
    # All raw API keys are strictly forbidden from being exposed or mutated through frontend schema payloads.
    # The application exclusively loads credentials from the private internal .env Vault and Server memory.

class SettingsResponse(BaseModel):
    success: bool
    message: str

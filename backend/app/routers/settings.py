from fastapi import APIRouter
from app.schemas.settings import AISettings, SettingsResponse
from app.config.settings import settings
import logging

router = APIRouter(prefix="/api/v2/settings", tags=["settings"])
logger = logging.getLogger("loom.settings")

@router.get("", response_model=AISettings)
async def get_settings():
    """获取当前系统配置"""
    return AISettings(
        default_llm_provider=settings.DEFAULT_LLM_PROVIDER,
        default_llm_model=settings.DEFAULT_LLM_MODEL,
        image_provider=settings.IMAGE_PROVIDER,
        tts_provider=settings.TTS_PROVIDER,
        video_provider=settings.VIDEO_PROVIDER,
    )

@router.post("", response_model=SettingsResponse)
async def update_settings(new_settings: AISettings):
    """更新系统配置 (持久化到内存/环境变量，实际生产应存入数据库或文件)"""
    # 这里我们仅作为演示更新内存中的 settings 对象
    # 在实际项目中，可能需要同步更新 .env 文件或数据库
    settings.DEFAULT_LLM_PROVIDER = new_settings.default_llm_provider
    settings.DEFAULT_LLM_MODEL = new_settings.default_llm_model
    settings.IMAGE_PROVIDER = new_settings.image_provider
    settings.TTS_PROVIDER = new_settings.tts_provider
    settings.VIDEO_PROVIDER = new_settings.video_provider
    
    # 注意：在真实的 Pydantic Settings 中，动态修改属性可能不生效（如果是从 ENV 加载的）
    # 但在这里为了演示前端效果，我们先这样处理
    logger.info("Settings updated successfully")
    return SettingsResponse(success=True, message="Settings updated")

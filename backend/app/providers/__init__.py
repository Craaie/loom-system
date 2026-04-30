"""
Provider 注册初始化。
在这里导入所有的 provider 模块，执行注册逻辑。
"""

from app.providers.base import ProviderRegistry

# 引入基础 mock provider，触发注册
import app.providers.mock

# 引入真实实现的 Providers，触发它们内部的 ProviderRegistry 注册
import app.providers.image.cogview
import app.providers.image.wanx
import app.providers.tts.dashscope
import app.providers.tts.fish
import app.providers.tts.minimax
import app.providers.video.hailuo

__all__ = ["ProviderRegistry"]

"""统一素材本地路径与公开 URL 的转换工具。"""

from __future__ import annotations

from urllib.parse import urlparse

PUBLIC_OUTPUT_PREFIX = "/output/"
LEGACY_PUBLIC_OUTPUT_PREFIX = "/api/v2/output/"
LOCAL_OUTPUT_PREFIX = "./output/"
BARE_OUTPUT_PREFIX = "output/"


def _normalize_separators(path: str) -> str:
    return (path or "").replace("\\", "/")


def to_public_asset_url(path: str) -> str:
    """将本地输出路径统一映射为前端可访问的 `/output/...` URL。"""
    normalized = _normalize_separators(path)
    if not normalized:
        return ""
    if normalized.startswith(("http://", "https://")):
        parsed = urlparse(normalized)
        normalized = parsed.path or normalized
    if normalized.startswith(LEGACY_PUBLIC_OUTPUT_PREFIX):
        return PUBLIC_OUTPUT_PREFIX + normalized[len(LEGACY_PUBLIC_OUTPUT_PREFIX):]
    if normalized.startswith(PUBLIC_OUTPUT_PREFIX):
        return normalized
    if normalized.startswith(LOCAL_OUTPUT_PREFIX):
        return PUBLIC_OUTPUT_PREFIX + normalized[len(LOCAL_OUTPUT_PREFIX):]
    if normalized.startswith(BARE_OUTPUT_PREFIX):
        return PUBLIC_OUTPUT_PREFIX + normalized[len(BARE_OUTPUT_PREFIX):]
    return normalized


def to_local_asset_path(path: str) -> str:
    """将公开 URL 或历史路径统一还原为本地 `./output/...` 路径。"""
    normalized = _normalize_separators(path)
    if not normalized:
        return ""
    if normalized.startswith(("http://", "https://")):
        parsed = urlparse(normalized)
        normalized = parsed.path or normalized
    if normalized.startswith(LEGACY_PUBLIC_OUTPUT_PREFIX):
        return LOCAL_OUTPUT_PREFIX + normalized[len(LEGACY_PUBLIC_OUTPUT_PREFIX):]
    if normalized.startswith(PUBLIC_OUTPUT_PREFIX):
        return LOCAL_OUTPUT_PREFIX + normalized[len(PUBLIC_OUTPUT_PREFIX):]
    if normalized.startswith(BARE_OUTPUT_PREFIX):
        return f"./{normalized}"
    return normalized


def build_asset_urls(local_path: str) -> dict[str, str]:
    """基于本地路径生成统一的本地/公开双路径字段。"""
    local = to_local_asset_path(local_path)
    return {
        "local_path": local,
        "public_url": to_public_asset_url(local),
    }


def pick_local_path(record: dict, *keys: str) -> str:
    """从任务记录中优先读取本地路径，兼容旧字段。"""
    for key in keys:
        value = record.get(key)
        if value:
            return to_local_asset_path(value)
    return ""

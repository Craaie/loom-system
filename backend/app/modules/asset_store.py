"""
Asset Store Module: 负责素材的哈希计算、缓存查询与持久化管理。
实现 "一次生成，多次复用"，降低 API 成本。

v2.1: 增加 JSON 文件持久化，缓存不再仅存于内存。
"""

import hashlib
import json
import logging
import os
import time
from typing import Dict, Any, Optional

from app.core.state import LoomState

logger = logging.getLogger("loom.asset_store")

# 持久化缓存文件路径
_CACHE_DIR = os.path.join(".", "output", ".asset_cache")
_CACHE_FILE = os.path.join(_CACHE_DIR, "manifest.json")


def _load_persistent_cache() -> Dict[str, Any]:
    """从磁盘加载持久化缓存"""
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"⚠️ 持久化缓存读取失败，使用空缓存: {e}")
    return {}


def _save_persistent_cache(manifest: Dict[str, Any]) -> None:
    """将缓存写回磁盘"""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"❌ 持久化缓存写入失败: {e}")


def generate_asset_hash(prompt: str, style: str, asset_type: str = "image") -> str:
    """
    根据提示词、风格和类型生成唯一的素材哈希。
    """
    payload = {
        "prompt": prompt,
        "style": style,
        "type": asset_type
    }
    dumped = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(dumped.encode()).hexdigest()


def get_cached_asset(state: LoomState, hash_key: str) -> Optional[Dict[str, Any]]:
    """
    从状态清单 + 磁盘缓存中查找已有的缓存资产。
    """
    # 先查内存 State
    manifest = state.get("asset_manifest", {})
    asset = manifest.get(hash_key)
    if asset and os.path.exists(asset.get("path", "")):
        logger.info(f"🎯 资产命中缓存 (State) [Hash: {hash_key[:8]}...]")
        return asset

    # 再查磁盘持久化
    persistent = _load_persistent_cache()
    asset = persistent.get(hash_key)
    if asset and os.path.exists(asset.get("path", "")):
        logger.info(f"🎯 资产命中缓存 (Disk) [Hash: {hash_key[:8]}...]")
        return asset

    return None


def save_asset_to_cache(state: LoomState, hash_key: str, path: str, asset_type: str) -> Dict[str, Any]:
    """
    记录新生成的资产到清单 + 磁盘缓存。
    """
    asset_entry = {
        "path": path,
        "type": asset_type,
        "ts": time.time()
    }

    # 同步写入磁盘持久化
    persistent = _load_persistent_cache()
    persistent[hash_key] = asset_entry
    _save_persistent_cache(persistent)

    # 返回增量，由 LoomState 的 reduce_dict 合并
    return {hash_key: asset_entry}


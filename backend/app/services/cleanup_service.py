"""
Cleanup Service: 物理文件与数据清理逻辑。
"""

import json
import logging
import os
import shutil

from app.config.settings import settings

logger = logging.getLogger("loom.cleanup_service")


def cleanup_thread_files(thread_id: str, session_id: str | None = None) -> None:
    """清理与 thread 关联的物理文件（输出资源 + 向量库）"""
    # 清理输出资源 (图片/视频/音频)
    output_dir = os.path.join("output", thread_id)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)
        logger.info(f"📁 已清理输出目录: {output_dir}")

    # 清理向量库缓存
    if session_id:
        chroma_dir = os.path.join(settings.CHROMA_PERSIST_DIRECTORY, session_id)
        if os.path.exists(chroma_dir):
            shutil.rmtree(chroma_dir, ignore_errors=True)
            logger.info(f"🧬 已清理向量库: {chroma_dir}")


def extract_session_id_from_checkpoint(checkpoint_data: bytes | str) -> str | None:
    """从 checkpoint 数据中提取 session_id（尽力而为）"""
    try:
        import pickle
        if isinstance(checkpoint_data, bytes):
            try:
                data = pickle.loads(checkpoint_data)
            except Exception:
                data = json.loads(checkpoint_data.decode("utf-8", errors="ignore"))
        else:
            data = json.loads(checkpoint_data)

        if isinstance(data, dict):
            # LangGraph 0.1+ 状态值存在 channel_values 里
            channel_vals = data.get("channel_values", data)
            if isinstance(channel_vals, dict):
                return channel_vals.get("session_id")
    except Exception as e:
        logger.debug(f"Failed to extract session_id: {e}")
    return None

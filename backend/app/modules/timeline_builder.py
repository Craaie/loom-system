"""
Timeline Builder: 基于分镜、图像和音频任务，精确计算每段素材的时间轴。
"""

import logging
import os
from typing import Dict, Any, List, Optional

from pydantic import BaseModel

from app.modules.asset_paths import pick_local_path

logger = logging.getLogger("loom.timeline")


class TimelineEntry(BaseModel):
    """单段时间轴条目"""
    scene_index: int
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 5.0
    asset_type: str = "image"
    asset_path: str = ""
    audio_path: Optional[str] = None
    subtitle_text: Optional[str] = None


class TimelineBuilder:
    """根据分镜数据和已生成素材，精确计算每段的起止时间。"""

    @staticmethod
    def _get_audio_duration(audio_path: str) -> Optional[float]:
        if not audio_path or not os.path.exists(audio_path):
            return None
        try:
            import subprocess

            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception as e:
            logger.warning("⚠️ 无法获取音频时长 (%s): %s", audio_path, e)
        return None

    @classmethod
    def build(
        cls,
        storyboard: List[Dict[str, Any]],
        image_tasks: List[Dict[str, Any]],
        audio_tasks: List[Dict[str, Any]],
        video_tasks: List[Dict[str, Any]],
    ) -> List[TimelineEntry]:
        img_map = {t.get("task_id", ""): t for t in image_tasks if t.get("status") == "done"}
        aud_map = {t.get("task_id", ""): t for t in audio_tasks if t.get("status") == "done"}
        vid_map = {t.get("task_id", ""): t for t in video_tasks if t.get("status") == "done"}

        timeline: List[TimelineEntry] = []
        current_time = 0.0

        for scene in storyboard:
            idx = scene.get("scene_index", 0)
            vid_key = f"video_{idx}"
            img_key = f"img_{idx}"
            aud_key = f"audio_{idx}"

            if vid_key in vid_map:
                asset_type = "video"
                asset_path = pick_local_path(vid_map[vid_key], "local_path", "video_path")
            elif img_key in img_map:
                asset_type = "image"
                asset_path = pick_local_path(img_map[img_key], "local_path", "image_path")
            else:
                logger.warning("⚠️ 场景 %s 无可用素材，跳过", idx)
                continue

            audio_path = pick_local_path(aud_map.get(aud_key, {}), "local_path", "audio_path")
            audio_duration = cls._get_audio_duration(audio_path) if audio_path else None
            scene_duration = scene.get("duration_seconds", scene.get("duration", 5.0))
            duration = max(audio_duration, 2.0) if audio_duration and audio_duration > 0 else float(scene_duration)

            timeline.append(
                TimelineEntry(
                    scene_index=idx,
                    start_time=current_time,
                    end_time=current_time + duration,
                    duration=duration,
                    asset_type=asset_type,
                    asset_path=asset_path,
                    audio_path=audio_path or None,
                    subtitle_text=scene.get("narration") or scene.get("dialogue"),
                )
            )
            current_time += duration

        logger.info("📐 时间轴构建完成：%s 段，总时长 %.1fs", len(timeline), current_time)
        return timeline

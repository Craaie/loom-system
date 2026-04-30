"""
FFmpegAssembler: 视频片段归一化、音频合成与字幕压制。

职责对照: docs/loom_03_detailed_design.md §1.4
实现顺序: docs/implementation-plan-v1.md §3.6 (Sprint 4)
"""

import json
import logging
import os
import platform
import shutil
import subprocess
import asyncio
import unicodedata
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger("loom.ffmpeg")


# ---------------------------------------------------------------------------
# Pydantic 模型 (对齐 loom_03_detailed_design.md §1.4)
# ---------------------------------------------------------------------------


class VideoProfile(str, Enum):
    """预设视频 Profile"""
    LANDSCAPE_1080P = "1920x1080"
    PORTRAIT_9_16 = "1080x1920"
    SQUARE = "1280x1280"


class VideoSegment(BaseModel):
    """单个视频片段的标准化输入（对齐 detailed_design）"""
    segment_id: str
    file_path: str                              # 视频片段本地路径
    resolution: str = "1920x1080"               # 目标分辨率
    fps: int = 30                               # 目标帧率
    codec: str = "h264"                         # 编码格式
    subtitle_text: Optional[str] = None         # 该片段对应的字幕文本
    subtitle_start_ms: Optional[int] = None     # 字幕起始时间 (ms)
    subtitle_end_ms: Optional[int] = None       # 字幕结束时间 (ms)
    duration: float = 5.0                       # 片段时长 (秒)
    audio_path: Optional[str] = None            # 旁白音频本地路径


class AssemblyConfig(BaseModel):
    """FFmpeg 合成配置"""
    width: int = 1280
    height: int = 1280
    fps: int = 24
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    pixel_format: str = "yuv420p"
    # 平台感知字体配置 (impl-plan §4)
    font_name: str = Field(
        default_factory=lambda: (
            "Arial Unicode MS" if platform.system() == "Darwin" else "DejaVu Sans"
        )
    )
    fonts_dir: str = Field(
        default_factory=lambda: (
            "/System/Library/Fonts/Supplemental"
            if platform.system() == "Darwin"
            else "/usr/share/fonts/truetype/dejavu"
        )
    )
    # 错误回退配置
    max_retries: int = 2
    cleanup_temp: bool = True

    @classmethod
    def from_profile(cls, profile: VideoProfile, **kwargs: Any) -> "AssemblyConfig":
        """从预设 Profile 快速创建配置"""
        w, h = profile.value.split("x")
        return cls(width=int(w), height=int(h), **kwargs)


class FFmpegError(Exception):
    """FFmpeg 执行失败"""
    pass


class FFmpegAssembler:
    """
    FFmpegAssembler: 负责视频片段归一化、音频合成与字幕压制。

    对照设计文档:
    - 输入: List[VideoSegment] (Pydantic 强约束)
    - 归一化: 自动检测分辨率/帧率/编码，不一致时统一转码
    - 字幕: 基于累积时长计算绝对时间偏移
    - 错误回退: 清理临时文件 + 重试 → 降级为图片轮播
    """

    def __init__(
        self,
        config: Optional[AssemblyConfig] = None,
        skip_check: bool = False,
    ):
        self.config = config or AssemblyConfig()
        if not skip_check:
            self._check_ffmpeg()

    def _check_ffmpeg(self) -> None:
        """检查 FFmpeg 是否安装"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, check=True
            )
            logger.info("✅ 成功检测到 FFmpeg 环境。")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error(
                "FFmpeg not found. Please install FFmpeg to use this module."
            )
            raise RuntimeError("FFmpeg is required but not found.")

    # ------------------------------------------------------------------
    # 字幕生成
    # ------------------------------------------------------------------

    def _generate_srt(
        self, segments: List[VideoSegment], output_path: str
    ) -> None:
        """生成 SRT 字幕文件，基于片段累积时长自动计算时间轴"""
        srt_content: List[str] = []
        current_time = 0.0

        for i, seg in enumerate(segments):
            text = seg.subtitle_text or ""
            if not text:
                current_time += seg.duration
                continue

            start_time = self._format_srt_time(current_time)
            end_time = self._format_srt_time(current_time + seg.duration)

            # 智能换行：按显示宽度计算（CJK 字符算 2 宽度）
            wrapped = self._wrap_subtitle(text, max_display_width=30)

            srt_content.append(f"{i + 1}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(f"{wrapped}\n")

            current_time += seg.duration

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_content))

    @staticmethod
    def _wrap_subtitle(text: str, max_display_width: int = 30) -> str:
        """按照显示宽度换行（CJK 字符宽度 = 2）"""
        lines: List[str] = []
        current_line = ""
        current_width = 0

        for char in text:
            char_width = 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
            if current_width + char_width > max_display_width:
                lines.append(current_line)
                current_line = char
                current_width = char_width
            else:
                current_line += char
                current_width += char_width

        if current_line:
            lines.append(current_line)
        return "\n".join(lines)

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    # ------------------------------------------------------------------
    # 导演系统：镜头动效 (Zoom/Pan / Ken Burns)
    # ------------------------------------------------------------------

    async def _apply_ken_burns(
        self, input_img: str, output_video: str, duration: float = 5.0
    ) -> None:
        """
        为图片应用 Ken Burns 效果（缓慢缩放平移），使其“动”起来。
        """
        cfg = self.config
        # 典型的 Ken Burns 滤镜公式: 缩放从 1.0 到 1.25
        # zoompan=z='zoom+0.001':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=...
        zf = f"zoom+0.0005" if duration > 3 else "zoom+0.001"
        vf = (
            f"scale={cfg.width*2}:{cfg.height*2}," # 先放大以防锯齿
            f"zoompan=z='{zf}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={int(cfg.fps * duration)}:s={cfg.width}x{cfg.height},"
            f"fps={cfg.fps}"
        )
        
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", input_img,
            "-vf", vf,
            "-c:v", cfg.video_codec,
            "-pix_fmt", cfg.pixel_format,
            "-t", str(duration),
            output_video,
        ]
        
        logger.info(f"🎬 应用导演动效 (ZoomPan): {input_img} -> {output_video}")
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await process.communicate()
        
        if process.returncode != 0:
            raise FFmpegError(f"ZoomPan failed for {input_img}")

    # ------------------------------------------------------------------
    # 视频归一化
    # ------------------------------------------------------------------

    async def _normalize_clip(
        self, input_video: str, output_video: str
    ) -> None:
        """
        将视频片段归一化为统一的分辨率、帧率和编码格式。
        确保 concat 时所有片段参数一致，避免合成失败。
        """
        cfg = self.config
        cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-vf", f"scale={cfg.width}:{cfg.height}:force_original_aspect_ratio=decrease,"
                   f"pad={cfg.width}:{cfg.height}:(ow-iw)/2:(oh-ih)/2,"
                   f"fps={cfg.fps}",
            "-c:v", cfg.video_codec,
            "-pix_fmt", cfg.pixel_format,
            "-c:a", cfg.audio_codec,
            "-ar", "44100",
            "-shortest",
            output_video,
        ]

        logger.info(f"🔧 归一化视频片段: {input_video} -> {output_video}")
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode(errors="replace")[:300]
            raise FFmpegError(f"Normalize failed for {input_video}: {error_msg}")

    # ------------------------------------------------------------------
    # 核心合成
    # ------------------------------------------------------------------

    async def assemble(
        self,
        segments: List[VideoSegment],
        output_file: str,
        audio_paths: Optional[List[str]] = None,
        bgm_path: Optional[str] = None,
        bgm_volume: float = 0.2,
        thread_id: str = "unknown",
    ) -> str:
        """
        核心合成流程：
        1. 片段归一化 (分辨率/帧率/编码)
        2. 字幕生成 (SRT，累积时间轴)
        3. concat 拼接
        4. 音频合成 (旁白 + BGM)
        5. 错误回退 (重试 → 降级图片轮播)
        """
        work_dir = os.path.dirname(os.path.abspath(output_file))
        temp_dir = os.path.join(work_dir, "temp_assembly")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            return await self._do_assemble(
                segments, output_file, temp_dir, audio_paths, bgm_path, bgm_volume, thread_id
            )
        except FFmpegError as e:
            logger.warning(f"⚠️ [任务-{thread_id}] 合成失败，尝试降级为图片轮播方案: {e}")
            return await self._fallback_slideshow(segments, output_file, temp_dir, thread_id)
        finally:
            if self.config.cleanup_temp and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info("Cleaned up temp directory: %s", temp_dir)
                except OSError as e:
                    logger.warning(f"⚠️ [任务-{thread_id}] 清理临时目录失败: {e}")

    async def _do_assemble(
        self,
        segments: List[VideoSegment],
        output_file: str,
        temp_dir: str,
        audio_paths: Optional[List[str]],
        bgm_path: Optional[str],
        bgm_volume: float,
        thread_id: str,
    ) -> str:
        """实际合成逻辑（可被 assemble 捕获异常后降级）"""

        # 1. 素材预处理 (归一化/动效生成)
        processed_clips: List[str] = []
        for i, seg in enumerate(segments):
            if not os.path.exists(seg.file_path):
                raise FFmpegError(f"❌ [任务-{thread_id}] 找不到素材文件: {seg.file_path}")
            
            output_path = os.path.join(temp_dir, f"clip_{i}.mp4")
            
            # 智能判断：图片 vs 视频
            is_image = seg.file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
            
            if is_image:
                # 图片资产 -> 应用导演镜头动效 (Zoom/Pan)
                await self._apply_ken_burns(seg.file_path, output_path, duration=seg.duration)
            else:
                # 视频资产 -> 执行标准归一化
                await self._normalize_clip(seg.file_path, output_path)
                
            processed_clips.append(output_path)

        # 2. 生成字幕
        srt_path = os.path.join(temp_dir, "subtitles.srt")
        self._generate_srt(segments, srt_path)

        # 3. concat 列表
        concat_file = os.path.join(temp_dir, "concat.txt")
        with open(concat_file, "w") as f:
            for path in processed_clips:
                safe_path = path.replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        # 4. 构建最终 FFmpeg 命令
        filter_complex: List[str] = []
        input_args = ["-f", "concat", "-safe", "0", "-i", concat_file]

        # 字幕滤镜
        safe_srt = srt_path.replace("\\", "/").replace(":", "\\:")
        sub_filter = (
            f"subtitles='{safe_srt}':"
            f"fontsdir='{self.config.fonts_dir}':"
            f"force_style='Fontname={self.config.font_name},Fontsize=20,"
            f"PrimaryColour=&Hffffff&,OutlineColour=&H000000&,"
            f"Outline=1,Shadow=1,Alignment=2'"
        )

        # 音频合成
        if audio_paths:
            for a_path in audio_paths:
                input_args.extend(["-i", a_path])

            concat_a = "".join(
                f"[{i + 1}:a]" for i in range(len(audio_paths))
            )
            filter_complex.append(
                f"{concat_a}concat=n={len(audio_paths)}:v=0:a=1[narration]"
            )

            if bgm_path:
                input_args.extend(["-i", bgm_path])
                bgm_idx = len(audio_paths) + 1
                filter_complex.append(
                    f"[{bgm_idx}:a]volume={bgm_volume}[bgm];"
                    f"[narration][bgm]amix=inputs=2:"
                    f"duration=first:dropout_transition=2[out_a]"
                )
            else:
                filter_complex.append("[narration]copy[out_a]")

        # 最终命令
        cmd = ["ffmpeg", "-y"] + input_args
        vf_chain = sub_filter

        if filter_complex:
            cmd.extend(["-filter_complex", ";".join(filter_complex)])
            audio_map = "[out_a]" if audio_paths else "0:a"
            cmd.extend(["-map", "0:v", "-vf", vf_chain, "-map", audio_map])
        else:
            cmd.extend(["-vf", vf_chain, "-c:a", "copy"])

        cmd.extend([
            "-c:v", self.config.video_codec,
            "-pix_fmt", self.config.pixel_format,
            "-shortest",
            output_file,
        ])

        logger.info("Executing FFmpeg assembly command")
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode(errors="replace")[:500]
            raise FFmpegError(
                f"❌ [任务-{thread_id}] FFmpeg 合成指令执行失败 (退出码 {process.returncode}): {error_msg}"
            )
 
        logger.info(f"✨ [任务-{thread_id}] 本阶段完成: {output_file}")
        return output_file

    # ------------------------------------------------------------------
    # 错误降级：图片轮播版本
    # ------------------------------------------------------------------

    async def _fallback_slideshow(
        self,
        segments: List[VideoSegment],
        output_file: str,
        temp_dir: str,
        thread_id: str,
    ) -> str:
        """
        降级方案：从视频片段截取首帧图片，拼成图片轮播视频。
        对照: loom_03_detailed_design §1.4 "连续失败后降级为仅导出图片轮播版本"
        """
        logger.warning(f"🚨 [任务-{thread_id}] 进入降级模式：正在创建图片轮播视频...")
        frames: List[str] = []

        for i, seg in enumerate(segments):
            frame_path = os.path.join(temp_dir, f"frame_{i}.jpg")
            if os.path.exists(seg.file_path):
                cmd = [
                    "ffmpeg", "-y", "-i", seg.file_path,
                    "-vframes", "1", "-q:v", "2",
                    frame_path,
                ]
                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                await process.communicate()
                if process.returncode == 0 and os.path.exists(frame_path):
                    frames.append(frame_path)

        if not frames:
            raise FFmpegError("Fallback failed: no frames could be extracted")

        # 用图片列表生成轮播视频（每张 5 秒）
        concat_file = os.path.join(temp_dir, "slideshow.txt")
        with open(concat_file, "w") as f:
            for frame in frames:
                safe = frame.replace("\\", "/")
                f.write(f"file '{safe}'\nduration 5\n")
            # 最后一帧需要重复引用（FFmpeg concat demuxer 要求）
            f.write(f"file '{frames[-1].replace(chr(92), '/')}'\n")

        fallback_output = output_file.replace(".mp4", "_slideshow.mp4")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-vf", f"scale={self.config.width}:{self.config.height}:"
                   f"force_original_aspect_ratio=decrease,"
                   f"pad={self.config.width}:{self.config.height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", self.config.video_codec,
            "-pix_fmt", self.config.pixel_format,
            fallback_output,
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await process.communicate()

        if process.returncode != 0:
            raise FFmpegError(f"❌ [任务-{thread_id}] 图片轮播降级方案也失败了")
 
        logger.info(f"✅ [任务-{thread_id}] 轮播视频已生成: {fallback_output}")
        return fallback_output

import pytest
from unittest.mock import patch

from app.modules.ffmpeg_tools import FFmpegAssembler, VideoSegment


@pytest.fixture
def assembler():
    with patch.object(FFmpegAssembler, "_check_ffmpeg", return_value=None):
        return FFmpegAssembler()


def test_ffmpeg_srt_generation_uses_subtitle_text(assembler, tmp_path):
    segments = [
        VideoSegment(segment_id="scene_1", file_path="scene_1.mp4", duration=2.0, subtitle_text="第一幕内容", audio_path="/tmp/a1.mp3"),
        VideoSegment(segment_id="scene_2", file_path="scene_2.mp4", duration=3.0, subtitle_text="第二幕内容", audio_path="/tmp/a2.mp3"),
    ]
    srt_path = tmp_path / "test.srt"
    assembler._generate_srt(segments, str(srt_path))

    content = srt_path.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:02,000" in content
    assert "第一幕内容" in content
    assert "/tmp/a1.mp3" not in content
    assert "00:00:02,000 --> 00:00:05,000" in content

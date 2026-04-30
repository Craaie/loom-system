import os
import json
import uuid
import zipfile
import shutil
from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger("loom.jianying_exporter")

def _generate_id() -> str:
    """生成符合剪映需要的 UUID (无横线)"""
    return uuid.uuid4().hex.upper()

def create_base_draft_info() -> Dict[str, Any]:
    """创建剪映 draft_info.json 的基础骨架"""
    return {
        "canvas_config": {
            "height": 1080,
            "width": 1920,
            "ratio": "16:9"
        },
        "materials": {
            "audio": [],
            "video": [],
            "texts": [],
            "transitions": []
        },
        "tracks": [],
        "version": 330000,
        "id": _generate_id()
    }

def create_meta_info(project_name: str) -> Dict[str, Any]:
    """创建剪映 draft_meta_info.json"""
    return {
        "draft_id": _generate_id(),
        "draft_name": project_name,
        "draft_materials": [],
        "tm_draft_create": 0,
        "tm_draft_modified": 0
    }

def export_to_jianying_zip(project_name: str, video_segments: List[Dict[str, Any]], audio_segments: List[Dict[str, Any]], output_zip_path: str) -> str:
    """
    将视频和音频时间轴数据打包导出为剪映工程 ZIP 压缩包 (JianYing Draft).
    
    Args:
        project_name: 工程名，如 "loom_chapter_1"
        video_segments: 视频段列表 [{"file_path": "/...", "duration_ms": 5000}]
        audio_segments: 音频段列表 [{"file_path": "/...", "start_ms": 0, "duration_ms": 3000}]
        output_zip_path: 目标 zip 文件路径
    
    Returns:
        最终的压缩包完整路径
    """
    temp_dir = Path("/tmp") / f"jy_draft_{project_name}_{uuid.uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        draft_info = create_base_draft_info()
        meta_info = create_meta_info(project_name)
        
        main_video_track = {
            "id": _generate_id(),
            "type": "video",
            "segments": []
        }
        main_audio_track = {
            "id": _generate_id(),
            "type": "audio",
            "segments": []
        }
        
        current_video_time_us = 0
        
        # 组装视频轨道
        for idx, seg in enumerate(video_segments):
            src_path = Path(seg["file_path"])
            if not src_path.exists():
                logger.warning(f"Video segment file missing: {src_path}")
                continue
                
            dest_name = f"video_{idx}{src_path.suffix}"
            dest_path = temp_dir / dest_name
            shutil.copy2(src_path, dest_path)
            
            mat_id = _generate_id()
            dur_us = seg.get("duration_ms", 5000) * 1000
            
            # 记录资产
            draft_info["materials"]["video"].append({
                "id": mat_id,
                "path": str(dest_path.absolute()),
                "duration": dur_us,
                "type": "video"
            })
            
            # 添加到轨道段
            main_video_track["segments"].append({
                "id": _generate_id(),
                "material_id": mat_id,
                "target_timerange": {
                    "start": current_video_time_us,
                    "duration": dur_us
                },
                "source_timerange": {
                    "start": 0,
                    "duration": dur_us
                }
            })
            current_video_time_us += dur_us

        # 组装混音旁白轨道
        for idx, seg in enumerate(audio_segments):
            src_path = Path(seg["file_path"])
            if not src_path.exists():
                logger.warning(f"Audio segment file missing: {src_path}")
                continue
                
            dest_name = f"audio_{idx}{src_path.suffix}"
            dest_path = temp_dir / dest_name
            shutil.copy2(src_path, dest_path)
            
            mat_id = _generate_id()
            dur_us = seg.get("duration_ms", 3000) * 1000
            start_us = seg.get("start_ms", 0) * 1000
            
            draft_info["materials"]["audio"].append({
                "id": mat_id,
                "path": str(dest_path.absolute()),
                "duration": dur_us,
                "type": "extract_music"
            })
            
            main_audio_track["segments"].append({
                "id": _generate_id(),
                "material_id": mat_id,
                "target_timerange": {
                    "start": start_us,
                    "duration": dur_us
                },
                "source_timerange": {
                    "start": 0,
                    "duration": dur_us
                }
            })

        draft_info["tracks"].extend([main_video_track, main_audio_track])
        
        # 写入 JSON
        with open(temp_dir / "draft_info.json", "w", encoding="utf-8") as f:
            json.dump(draft_info, f, ensure_ascii=False, indent=2)
            
        with open(temp_dir / "draft_meta_info.json", "w", encoding="utf-8") as f:
            json.dump(meta_info, f, ensure_ascii=False, indent=2)
            
        # 打包 ZIP
        logger.info(f"Packing JianYing draft to {output_zip_path} ...")
        with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in temp_dir.rglob('*'):
                if item.is_file():
                    arcname = item.relative_to(temp_dir)
                    zf.write(item, arcname)
                    
        return output_zip_path

    finally:
        # 清理临时文件
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

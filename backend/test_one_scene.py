import asyncio
import os
import sys

# 将项目根目录加入 sys.path 以支持 backend 导入
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.providers.image.wanx import WanxImageProvider
from app.providers.tts.dashscope import DashScopeTTSProvider
from app.config.settings import settings

async def test_single_scene():
    """测试单个分镜的生成：一张图 + 一段音频"""
    print("🚀 启动单分镜生成测试...")
    
    test_id = "test_run_001"
    output_dir = f"./output/{test_id}"
    os.makedirs(output_dir, exist_ok=True)
    
    # 模拟分镜数据
    scene = {
        "image_prompt": "A futuristic city with flying cars and neon lights, cinematic lighting",
        "visual_style": "Cyberpunk, 8k, detailed",
        "narration": "在未来的霓虹之城，飞车穿梭于高楼之间，光影交错。"
    }
    
    # 1. 测试 Wanx 生图
    print("\n🎨 [Step 1] 正在测试 Wanx 生图...")
    image_provider = WanxImageProvider()
    img_path = f"{output_dir}/test_image.jpg"
    
    img_result = await image_provider.generate(
        prompt=f"Professional storyboard, {scene['visual_style']}. {scene['image_prompt']}",
        style=scene['visual_style'],
        output_path=img_path
    )
    
    if img_result.status == "done":
        print(f"✅ 生图成功: {img_result.file_path}")
    else:
        print(f"❌ 生图失败: {img_result.error}")
        
    # 2. 测试 DashScope TTS
    print("\n🎙️ [Step 2] 正在测试 DashScope TTS...")
    tts_provider = DashScopeTTSProvider()
    audio_path = f"{output_dir}/test_audio.mp3"
    
    tts_result = await tts_provider.synthesize(
        text=scene['narration'],
        voice="longxiaochun",
        output_path=audio_path
    )
    
    if tts_result.status == "done":
        print(f"✅ 语音合成成功: {tts_result.file_path}")
    else:
        print(f"❌ 语音合成失败: {tts_result.error}")

    print("\n✨ 测试结束。请检查 output/test_run_001 目录。")

if __name__ == "__main__":
    asyncio.run(test_single_scene())

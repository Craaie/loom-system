"""
独立测试脚本：直接裸调 DashScope Wanx API，不依赖任何项目模块。
用于精确诊断 URL 提取失败的根因。
"""
import asyncio
import aiohttp
import os
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DASHSCOPE_API_KEY")
SUBMIT_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
POLL_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"


async def main():
    if not API_KEY:
        print("❌ DASHSCOPE_API_KEY 未配置")
        return

    headers = {
        "X-DashScope-Async": "enable",
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "wanx-v1",
        "input": {"prompt": "A cute cat sitting on a desk, digital art"},
        "parameters": {"style": "<photography>", "size": "1024*1024", "n": 1},
    }

    async with aiohttp.ClientSession() as session:
        # 1. 提交任务
        print("📤 提交绘图任务...")
        async with session.post(SUBMIT_URL, headers=headers, json=payload) as resp:
            submit_data = await resp.json()
            print(f"  Submit status: {resp.status}")
            print(f"  Submit body:   {json.dumps(submit_data, indent=2, ensure_ascii=False)}")
            task_id = submit_data.get("output", {}).get("task_id")
            if not task_id:
                print("❌ 没有拿到 task_id，退出")
                return

        # 2. 轮询
        poll_headers = {"Authorization": f"Bearer {API_KEY}"}
        for i in range(60):
            await asyncio.sleep(3)
            url = POLL_URL.format(task_id=task_id)
            async with session.get(url, headers=poll_headers) as poll_resp:
                poll_data = await poll_resp.json()
                status = poll_data.get("output", {}).get("task_status")
                print(f"  [{i}] poll status={status}")

                if status == "SUCCEEDED":
                    print("\n✅ 任务成功！完整响应:")
                    print(json.dumps(poll_data, indent=2, ensure_ascii=False))

                    # ---- 逐层解析测试 ----
                    output = poll_data.get("output")
                    print(f"\n  type(output) = {type(output)}")
                    
                    results = output.get("results") if output else None
                    print(f"  type(results) = {type(results)}")
                    print(f"  results = {results}")

                    if results and len(results) > 0:
                        first = results[0]
                        print(f"  type(first) = {type(first)}")
                        print(f"  first = {first}")
                        print(f"  first.keys() = {list(first.keys()) if isinstance(first, dict) else 'N/A'}")
                        
                        img_url = first.get("url") if isinstance(first, dict) else None
                        print(f"  img_url = {img_url}")
                        print(f"  type(img_url) = {type(img_url)}")

                        if img_url:
                            # 尝试下载
                            print(f"\n📥 下载图片: {img_url[:80]}...")
                            async with session.get(img_url) as img_resp:
                                print(f"  Download status: {img_resp.status}")
                                if img_resp.status == 200:
                                    os.makedirs("./output/test_raw", exist_ok=True)
                                    with open("./output/test_raw/test.png", "wb") as f:
                                        async for chunk in img_resp.content.iter_chunked(8192):
                                            f.write(chunk)
                                    size = os.path.getsize("./output/test_raw/test.png")
                                    print(f"  ✅ 下载完成! 文件大小: {size} bytes")
                                else:
                                    print(f"  ❌ 下载失败: {img_resp.status}")
                        else:
                            print("  ❌ first.get('url') 返回 None！")
                    else:
                        print("  ❌ results 为空或不是列表")
                    return

                elif status == "FAILED":
                    print(f"❌ 任务失败: {json.dumps(poll_data, indent=2)}")
                    return

        print("❌ 超时")


if __name__ == "__main__":
    asyncio.run(main())

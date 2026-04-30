import os
import aiohttp
import asyncio
import logging
from typing import Dict, Any
from app.providers.base import ImageProvider, GenerationResult, ProviderRegistry
from app.config.settings import settings

logger = logging.getLogger("loom.providers.wanx")

class WanxImageProvider(ImageProvider):
    name = "wanx"
    
    def __init__(self):
        self.api_key = getattr(settings, "DASHSCOPE_API_KEY", None)
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
        self.poll_url = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        self.model_name = "wanx-v1" 

    def _deep_extract_url(self, data: Any) -> str:
        """【终极方案】从报文全文中通过正则匹配提取 URL"""
        import re
        import json
        
        # 尝试多种转化为字符串的方式，确保覆盖所有情况
        try:
            raw_str = json.dumps(data)
        except:
            raw_str = str(data)
            
        # 模式 1: 寻找典型的阿里 OSS 结果路径 (兼容 \/ 转义)
        patterns = [
            r'https?[:\\/]+dashscope-result[^\s"\'\},]+', 
            r'https?[:\\/]+[^\s"\'\},]+oss-cn[^\s"\'\},]+'
        ]
        
        for p in patterns:
            match = re.search(p, raw_str)
            if match:
                url = match.group(0)
                # 清洗转义
                url = url.replace('\\', '')
                # 去掉尾部可能的引号或括号
                url = url.rstrip(')"\'}] ')
                if "http" in url:
                    return url
                    
        return None
        
    async def generate(self, prompt: str, style: str, output_path: str) -> GenerationResult:
        if not self.api_key or not self.api_key.get_secret_value():
            logger.warning("DashScope API key is not configured. Falling back to mock image.")
            from app.providers.mock import MockImageProvider
            return await MockImageProvider().generate(prompt, style, output_path)
            
        logger.info(f"🎨 [Aliyun-Wanx] Submitting task. Prompt: {prompt[:30]}...")
        
        headers = {
            "X-DashScope-Async": "enable",
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_name,
            "input": {
                "prompt": f"Style: {style}. {prompt}"
            },
            "parameters": {
                "style": "<photography>", 
                "size": "1024*1024",
                "n": 1
            }
        }
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # 1. 发起绘制请求获取任务 ID (带 429 退避重试)
                task_id = None
                max_submit_retries = 3
                for attempt in range(max_submit_retries):
                    async with session.post(self.api_url, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            task_id = data.get("output", {}).get("task_id")
                            if task_id:
                                break
                            else:
                                return GenerationResult(status="failed", error="No task_id from Wanx", provider=self.name)
                        
                        elif response.status == 429:
                            wait_time = (attempt + 1) * 2
                            logger.warning(f"⚠️ [Aliyun-Wanx] Rate Limit (429). Retrying in {wait_time}s... (Attempt {attempt+1}/{max_submit_retries})")
                            await asyncio.sleep(wait_time)
                            continue
                            
                        else:
                            err = await response.text()
                            logger.error(f"Wanx submit Error {response.status}: {err}")
                            return GenerationResult(status="failed", error=str(err), provider=self.name)
                
                if not task_id:
                    return GenerationResult(status="failed", error="Wanx submission failed after retries", provider=self.name)
                        
                logger.info(f"⏳ [Aliyun-Wanx] Task ID {task_id} generated. Starts polling...")
                
                # 2. 轮询状态
                poll_headers = {
                    "Authorization": f"Bearer {self.api_key.get_secret_value()}"
                }
                
                max_retries = 40 # 增加轮询次数，防止复杂绘图超时
                for _ in range(max_retries):
                    await asyncio.sleep(3)
                    async with session.get(self.poll_url.format(task_id=task_id), headers=poll_headers) as poll_resp:
                        if poll_resp.status == 200:
                            poll_data = await poll_resp.json()
                            status = poll_data.get("output", {}).get("task_status")
                            
                            if status == "SUCCEEDED":
                                img_url = None
                                # 强制使用 logger.error 打印调试信息，确保用户能看到
                                logger.error(f"🔎 [万象调试] 识别到任务成功。数据类型: {type(poll_data)}")
                                
                                # 1. 尝试所有可能的路径 (Dict/Object 兼容)
                                try:
                                    # 尝试标准 dict 路径
                                    if isinstance(poll_data, dict):
                                        res_list = poll_data.get("output", {}).get("results", [])
                                        if res_list and len(res_list) > 0:
                                            img_url = res_list[0].get("url") or res_list[0].get("img_url")
                                    
                                    # 尝试对象属性访问 (如果是 SDK Response 对象)
                                    if not img_url and hasattr(poll_data, "output"):
                                        out_obj = getattr(poll_data, "output")
                                        res_obj = getattr(out_obj, "results", [])
                                        if res_obj and len(res_obj) > 0:
                                            img_url = getattr(res_obj[0], "url", getattr(res_obj[0], "img_url", None))
                                except Exception as e:
                                    logger.error(f"🔎 [万象调试] 路径解析过程报错: {e}")
                                
                                # 2. 终极正则从原始文本中捞
                                if not img_url:
                                    logger.error("🔎 [万象调试] 标准路径未提取到 URL，启动正则粗暴搜索...")
                                    import re
                                    raw_text = str(poll_data)
                                    # 匹配任何 https:// 且包含 .com 的长链
                                    all_urls = re.findall(r'https?://[^\s\'"<>\}]+', raw_text)
                                    for u in all_urls:
                                        if "aliyuncs.com" in u:
                                            img_url = u.replace('\\/', '/').rstrip('\'"},')
                                            logger.error(f"🔎 [万象调试] 正则从文本中捞到了: {img_url[:60]}...")
                                            break
                                
                                if img_url:
                                    # 3. 下载图片 —— 必须用全新的干净 session，
                                    #    因为当前 session 带有 Authorization 头，
                                    #    OSS 签名 URL 遇到额外 Auth 会返回 403
                                    async with aiohttp.ClientSession() as dl_session:
                                        async with dl_session.get(img_url) as img_req:
                                            if img_req.status == 200:
                                                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                                                with open(output_path, "wb") as f:
                                                    async for chunk in img_req.content.iter_chunked(8192):
                                                        f.write(chunk)
                                                logger.info(f"✅ [Aliyun-Wanx] Image saved -> {output_path}")       
                                                return GenerationResult(
                                                    status="done", 
                                                    file_path=output_path, 
                                                    provider=self.name
                                                )
                                            else:
                                                logger.error(f"❌ [Aliyun-Wanx] 图片下载失败 HTTP {img_req.status}")
                                
                                # 最终失败
                                logger.error(f"❌ [Aliyun-Wanx] URL extraction failed. Payload: {poll_data}")
                                return GenerationResult(status="failed", error="URL extraction failed", provider=self.name)
                                
                            elif status == "FAILED":
                                err_msg = poll_data.get("output", {}).get("code", "Unknown Wanx Error")
                                logger.error(f"❌ [Aliyun-Wanx] Task failed: {err_msg}")
                                return GenerationResult(status="failed", error=err_msg, provider=self.name)
                                
                        elif poll_resp.status == 429:
                            # 轮询时遇到 429 也可以稍作等待
                            await asyncio.sleep(5)
                            
                return GenerationResult(status="failed", error="Wanx polling timeout", provider=self.name)

        except Exception as e:
            logger.error(f"❌ [Aliyun-Wanx] Exception: {e}")
            return GenerationResult(status="failed", error=str(e), provider=self.name)

# 注册引擎
ProviderRegistry.register_image("wanx", WanxImageProvider)

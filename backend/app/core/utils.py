import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("loom.utils")

def extract_json(text: str) -> Any:
    """
    从 LLM 响应中鲁棒地提取并解析 JSON 对象。
    策略优先级:
    1. 寻找 Markdown 代码块 (```json ... ``` 或 ``` ...)
    2. 寻找最外层的 { ... } 结构
    3. 直接解析全文本
    """
    if not text:
        return None

    cleaned = text.strip()
    
    # 1. 尝试匹配 Markdown 代码块
    # 使用正则表达式匹配 ```json 和 ``` 之间的内容
    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # 2. 核心鲁棒逻辑：寻找最外层的大括号
    # 使用正则表达式寻找第一个 { 和最后一个 }
    # 注意：这种方式在纯文本中包含多个独立 JSON 时可能失效，但在 Agent 场景中通常有效
    json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if json_match:
        potential_json = json_match.group(1)
        try:
            return json.loads(potential_json)
        except json.JSONDecodeError:
            # 如果最外层括号解析失败，尝试逐层收缩（应对前后多余字符）
            # 这种情况较少见，通常 regex 就够了
            pass

    # 3. 兜底：直接解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"JSON extraction failed. Original text: {text[:200]}...")
        raise e

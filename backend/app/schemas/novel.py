"""小说与卷次相关请求/响应模型"""

from pydantic import BaseModel
from typing import Optional


class NovelCreate(BaseModel):
    project_id: str
    title: str
    author: Optional[str] = ""


class VolumeCreate(BaseModel):
    novel_id: str
    title: str
    index: Optional[int] = 0

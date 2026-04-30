"""任务与审批相关请求/响应模型"""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from app.core.state import ApprovalStatus


class JobCreate(BaseModel):
    novel_content: Optional[str] = None
    volume_id: Optional[str] = None
    session_id: Optional[str] = None
    cost_limit: float = 10.0
    provider: Optional[str] = None  # LLM Provider
    model: Optional[str] = None     # LLM Model
    image_provider: Optional[str] = None
    tts_provider: Optional[str] = None
    video_provider: Optional[str] = None


class ApprovalUpdate(BaseModel):
    thread_id: str
    status: ApprovalStatus
    feedback: Optional[str] = None


class StateUpdate(BaseModel):
    """用于手动微调状态的请求模型"""
    storyboard_json: Optional[List[Dict[str, Any]]] = None
    character_registry: Optional[Dict[str, Any]] = None
    analysis_prompt: Optional[str] = None
    approval_status: Optional[ApprovalStatus] = None


class BatchDeleteRequest(BaseModel):
    thread_ids: List[str]

class RegenerateRequest(BaseModel):
    target: str
    new_prompt: Optional[str] = None

import pytest
from app.core.state import LoomState, ApprovalStatus
from app.core.supervisor import TaskClassifier, RoutingDecision
from app.config.settings import settings

def test_classifier_error_fallback():
    """测试错误率上升时降级到 Ollama (AI 降级)"""
    state = LoomState(
        session_id="test_session",
        thread_id="test_thread",
        novel_content="这是一段测试文本",
        character_registry={},
        storyboard_json=[],
        cost_accumulator=0.0,
        error_count=3,  # 触发 AI 降级阈值
        approval_status=ApprovalStatus.PENDING,
        retry_history=[],
        generation_mode="cloud",
        _routing_model_provider=None,
        _routing_model_name=None,
        cost_limit=10.0
    )
    decision = TaskClassifier.classify(state)
    assert decision.model_provider == "ollama"
    assert "local AI" in decision.reason

def test_classifier_exhausted_fallback():
    """测试错误率耗尽时重定向到终极兜底"""
    state = LoomState(
        session_id="test_session",
        thread_id="test_thread",
        novel_content="这是一段重试多次失败的文本",
        character_registry={},
        storyboard_json=[],
        cost_accumulator=0.0,
        error_count=5,  # 触发终极兜底阈值
        approval_status=ApprovalStatus.PENDING,
        retry_history=[],
        generation_mode="cloud",
        _routing_model_provider=None,
        _routing_model_name=None,
        cost_limit=10.0
    )
    decision = TaskClassifier.classify(state)
    assert decision.next_node == "END"
    assert decision.model_name == "static-fallback"
    assert "static fallback" in decision.reason

def test_classifier_cost_breaker():
    """测试成本接近阈值时触发降级"""
    state = LoomState(
        session_id="test_session",
        thread_id="test_thread",
        novel_content="这是一段非常复杂的文本",
        character_registry={},
        storyboard_json=[],
        cost_accumulator=9.0,  # 阈值 10.0 的 90%
        error_count=0,
        approval_status=ApprovalStatus.PENDING,
        retry_history=[],
        generation_mode="cloud",
        _routing_model_provider=None,
        _routing_model_name=None,
        cost_limit=10.0
    )
    decision = TaskClassifier.classify(state)
    assert decision.model_provider == "ollama"
    assert "Cost" in decision.reason

def test_classifier_simple_task():
    """测试简单任务路由到 Ollama"""
    state = LoomState(
        session_id="test_session",
        thread_id="test_thread",
        novel_content="短文本",
        character_registry={},
        storyboard_json=[],
        cost_accumulator=0.0,
        error_count=0,
        approval_status=ApprovalStatus.PENDING,
        retry_history=[],
        generation_mode="cloud",
        _routing_model_provider=None,
        _routing_model_name=None,
        cost_limit=10.0
    )
    decision = TaskClassifier.classify(state)
    assert decision.model_provider == "ollama"

def test_classifier_complex_task():
    """测试复杂任务路由到云端默认模型"""
    state = LoomState(
        session_id="test_session",
        thread_id="test_thread",
        novel_content="A memory-heavy long text with many detailed descriptions..." * 100,
        character_registry={"林晓": {"appearance": "描述"}},
        storyboard_json=[],
        cost_accumulator=0.0,
        error_count=0,
        approval_status=ApprovalStatus.PENDING,
        retry_history=[],
        generation_mode="cloud",
        _routing_model_provider=None,
        _routing_model_name=None,
        cost_limit=10.0
    )
    decision = TaskClassifier.classify(state)
    assert decision.model_provider == settings.DEFAULT_LLM_PROVIDER
    assert decision.model_name == settings.DEFAULT_LLM_MODEL

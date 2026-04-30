import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.engine import batch_analysis_node


@pytest.mark.asyncio
async def test_batch_analysis_node_promotes_story_context():
    state = {
        "session_id": "test-session",
        "batch_id": "parallel_test-session",
        "batch_status": "submitted",
        "batch_provider": "deepseek",
        "batch_model": "deepseek-chat",
        "analysis_prompt": "",
    }

    analyzer = MagicMock()
    analyzer.get_batch_status = AsyncMock(return_value={"status": "completed"})
    analyzer.get_full_registry.return_value = {"林晓": {"appearance": "白衣"}}
    analyzer.get_story_context.return_value = [
        {"index": 0, "title": "第一章", "summary": "主角初登场"},
        {"index": 1, "title": "第二章", "summary": "冲突建立"},
    ]

    with patch("app.core.engine.ParallelAnalyzer", return_value=analyzer):
        result = await batch_analysis_node(state)

    assert result["batch_status"] == "completed"
    assert result["chapter_index"] == 1
    assert result["global_context"]["chapter_count"] == 2
    assert result["global_context"]["chapter_summaries"][0]["summary"] == "主角初登场"

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.story.storyboard import StoryboardAgent, StoryboardOutput, Scene, _format_story_context


def test_format_story_context_uses_chapter_summaries():
    state = {
        "global_context": {
            "chapter_summaries": [
                {"index": 0, "title": "第一章", "summary": "主角登场"},
                {"index": 1, "title": "第二章", "summary": "冲突升级"},
            ]
        }
    }
    context = _format_story_context(state)
    assert "第一章" in context
    assert "冲突升级" in context


@pytest.mark.asyncio
async def test_storyboard_generation_success():
    mock_llm = MagicMock()
    structured_llm = MagicMock()
    structured_llm.ainvoke = AsyncMock(return_value=StoryboardOutput(
        scenes=[
            Scene(
                scene_index=1,
                source_text="测试原文",
                image_prompt="A cinematic close-up of the protagonist",
                characters=["主角"],
                visual_style="Moody lighting",
                narration="测试旁白",
                duration_seconds=5,
            )
        ],
        global_style="写实"
    ))
    mock_llm.with_structured_output.return_value = structured_llm

    with patch("app.agents.story.storyboard.VectorStoreManager") as mock_vsm:
        mock_vsm.return_value.get_contextual_profile.return_value = {}
        agent = StoryboardAgent(mock_llm)
        state = {
            "novel_content": "测试文本",
            "character_registry": {},
            "global_context": {"chapter_summaries": [{"index": 0, "title": "第一章", "summary": "主角登场"}]},
            "cost_accumulator": 0.0,
            "cost_limit": 10.0,
            "session_id": "test",
            "thread_id": "test_thread",
            "chapter_index": 0,
        }
        result = await agent.generate_storyboard(state)

    assert "storyboard_json" in result
    assert len(result["storyboard_json"]) == 1
    assert result["approval_status"] == "storyboard_pending"
    assert result["storyboard_json"][0]["narration"] == "测试旁白"

from app.memory.memory_config import parse_memory_config
from app.memory.projectors.skill import SkillMemoryProjector
from app.memory.projectors.utils import ensure_dict
from app.memory.slimmer import HistoryProjection


def test_ensure_dict_parses_json_string():
    assert ensure_dict('{"skill_name": "topic-daily-analysis"}') == {
        "skill_name": "topic-daily-analysis"
    }


def test_skill_projector_handles_string_arguments():
    cfg = parse_memory_config({}).slim
    projector = SkillMemoryProjector()
    result = projector.slim_result(
        tool_name="load_skill",
        content="long skill body",
        metadata={
            "tool_name": "load_skill",
            "arguments": '{"skill_name": "topic-daily-analysis"}',
        },
        config=cfg,
    )
    assert result.content == "已加载 Skill: topic-daily-analysis"


def test_history_projection_skill_row_with_string_arguments():
    memory_config = parse_memory_config({})
    projection = HistoryProjection()
    rows = [
        {
            "role": "tool",
            "message_type": "skill_load",
            "content": "SKILL.md body",
            "sequence": 1,
            "metadata": {
                "tool_name": "load_skill",
                "arguments": '{"skill_name": "topic-daily-analysis"}',
            },
        }
    ]
    projected = projection.project_rows(rows, memory_config)
    assert projected[0]["content"] == "已加载 Skill: topic-daily-analysis"

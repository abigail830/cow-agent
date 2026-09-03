from app.memory.memory_config import parse_memory_config


def test_parse_memory_config_defaults():
    cfg = parse_memory_config({})
    assert cfg.working_set_turns == 20
    assert cfg.cold_resume_max_turns == 10
    assert cfg.slim.enabled is True
    assert cfg.slim.default_preview_chars == 200


def test_parse_memory_config_from_profile():
    cfg = parse_memory_config(
        {
            "memory": {
                "working_set_turns": 15,
                "cold_resume_max_turns": 8,
                "slim": {
                    "enabled": False,
                    "default_preview_chars": 100,
                    "tools": {"postgres_query_data": {"request_chars": 120}},
                },
            }
        }
    )
    assert cfg.working_set_turns == 15
    assert cfg.cold_resume_max_turns == 8
    assert cfg.slim.enabled is False
    assert cfg.slim.request_chars_for("postgres_query_data") == 120
    assert cfg.slim.request_chars_for("unknown_tool") == 100


def test_config_hash_changes_with_settings():
    a = parse_memory_config({"memory": {"working_set_turns": 20}})
    b = parse_memory_config({"memory": {"working_set_turns": 21}})
    assert a.config_hash() != b.config_hash()

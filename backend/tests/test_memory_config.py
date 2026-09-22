from app.platform.memory.memory_config import parse_memory_config


def test_default_memory_config():
    cfg = parse_memory_config({})
    assert cfg.slim.enabled is True
    assert cfg.compaction.enabled is True
    assert cfg.compaction.truncation_threshold == 0.9
    assert cfg.compaction.summarization.target_count == 20


def test_parse_compaction_from_profile():
    cfg = parse_memory_config(
        {
            "memory": {
                "compaction": {
                    "truncation_threshold": 0.85,
                    "summarization": {"target_count": 15, "threshold": 3},
                }
            }
        }
    )
    assert cfg.compaction.truncation_threshold == 0.85
    assert cfg.compaction.summarization.target_count == 15
    assert cfg.compaction.summarization.threshold == 3


def test_config_hash_changes_when_compaction_changes():
    a = parse_memory_config({"memory": {"compaction": {"truncation_threshold": 0.9}}})
    b = parse_memory_config({"memory": {"compaction": {"truncation_threshold": 0.8}}})
    assert a.config_hash() != b.config_hash()

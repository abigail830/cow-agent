from app.memory.long_term.commands import _parse_command
from app.memory.long_term.formatter import format_for_injection, parse_bullets, validate_line
from app.memory.memory_config import parse_memory_config


def test_parse_memory_config_long_term_defaults():
    cfg = parse_memory_config({})
    assert cfg.long_term.enabled is True
    assert cfg.long_term.inject_max_tokens == 1500


def test_validate_line_constraint():
    assert validate_line("[!] 不要用表格") == "[!] 不要用表格"
    assert validate_line("不要用表格") == "- 不要用表格"


def test_format_for_injection_includes_policy_and_blocks():
    block = format_for_injection(
        "[!] 不要猜测\n- 回复用中文",
        "- 默认 30 天",
        agent_slug="yl-worker1",
        max_tokens=1500,
    )
    assert "<memory_policy>" in block
    assert "<user_preferences>" in block
    assert 'agent="yl-worker1"' in block
    assert "[!] 不要猜测" in block


def test_parse_bullets_constraint_and_preference():
    rows = parse_bullets("[!] 不要表格\n- 用中文")
    assert rows == [("[!]", "不要表格"), ("-", "用中文")]


def test_parse_explicit_remember_command():
    parsed = _parse_command("记住：回复用中文")
    assert parsed is not None
    assert parsed.action == "append"
    assert parsed.payload == "回复用中文"


def test_parse_non_memory_message_ignored():
    assert _parse_command("帮我分析一下最近的数据趋势") is None


def test_parse_constraint_command():
    parsed = _parse_command("不要总是用饼图")
    assert parsed is not None
    assert parsed.action == "constraint"
    assert "饼图" in parsed.payload


def test_parse_forget_command():
    parsed = _parse_command("忘掉：回复用中文")
    assert parsed is not None
    assert parsed.action == "remove"

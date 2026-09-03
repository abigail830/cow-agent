import json

from app.middleware.result_truncator import (
    extract_response_text,
    truncate_observation_text,
    truncate_tool_response,
)


def test_skips_small_payload():
    text = json.dumps({"rows": [{"a": 1}], "row_count": 1})
    assert truncate_observation_text(text, max_bytes=50_000) == text


def test_summarizes_large_json_rows():
    rows = [{"id": i, "value": "x" * 200} for i in range(100)]
    text = json.dumps({"rows": rows, "row_count": 100})
    out = truncate_observation_text(text, max_bytes=500)
    data = json.loads(out)
    assert data["truncated"] is True
    assert data["row_count"] == 100
    assert len(data["sample_rows"]) == 5


def test_truncates_plain_text():
    text = "a" * 10_000
    out = truncate_observation_text(text, max_bytes=100)
    assert out.endswith("…[truncated]")
    assert len(out.encode("utf-8")) <= 100 + len("…[truncated]".encode("utf-8"))


def test_wrap_preserves_string_result():
    big = json.dumps({"rows": [{"n": i} for i in range(200)]})
    truncated = truncate_tool_response(big, max_bytes=200)
    assert isinstance(truncated, str)
    assert json.loads(truncated)["truncated"] is True


def test_extract_from_mcp_content_blocks():
    payload = {"content": [{"type": "text", "text": '{"rows": []}'}]}
    assert extract_response_text(payload) == '{"rows": []}'

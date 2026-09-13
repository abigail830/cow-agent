import json

from app.platform.attachments.tool_result_slim import (
    build_persisted_attachment_payload,
    slim_attachment_tool_row,
    slim_attachment_tool_payload,
)
from app.platform.chat.run_service import _apply_attachment_persist_strip
from app.platform.memory.memory_config import AttachmentPullConfig, MemoryConfig
from app.platform.memory.projectors.attachment_pull import AttachmentPullMemoryProjector
from app.platform.memory.memory_config import parse_memory_config
from app.platform.memory.slimmer import HistoryProjection


def test_build_persisted_payload_strips_base64() -> None:
    payload = {
        "status": "ok",
        "attachment_id": "a1",
        "filename": "chart.png",
        "data_base64": "A" * 50_000,
        "question": "What is shown?",
    }
    slimmed = build_persisted_attachment_payload("analyze_image", payload, max_chars=4096)
    assert "data_base64" not in slimmed
    assert slimmed["attachment_id"] == "a1"
    assert slimmed["full_available"] is True
    assert slimmed["persisted_summary"] is True
    assert "summary" in slimmed


def test_build_persisted_payload_truncates_read_content() -> None:
    payload = {
        "status": "ok",
        "attachment_id": "a2",
        "filename": "report.docx",
        "content": "x" * 20_000,
    }
    slimmed = build_persisted_attachment_payload("read_attachment", payload, max_chars=500)
    assert "content" not in slimmed
    assert len(slimmed["summary"]) <= 501  # preview_text may append ellipsis


def test_slim_attachment_tool_payload_serializes_json() -> None:
    content, metadata = slim_attachment_tool_payload(
        "read_attachment",
        content=None,
        metadata={
            "tool_name": "read_attachment",
            "result": {
                "status": "ok",
                "attachment_id": "a3",
                "content": "hello " * 10_000,
            },
        },
        max_chars=200,
    )
    assert content is not None
    parsed = json.loads(content)
    assert parsed["persisted_summary"] is True
    assert "content" not in parsed
    assert len(parsed["summary"]) <= 201
    assert metadata["attachment_persist_slimmed"] is True


def test_slim_attachment_tool_row_on_streamed_result() -> None:
    row = {
        "role": "tool",
        "message_type": "tool_result",
        "content": None,
        "metadata": {
            "tool_name": "analyze_image",
            "result": {
                "status": "ok",
                "attachment_id": "img-1",
                "data_base64": "Z" * 100_000,
            },
        },
    }
    slimmed = slim_attachment_tool_row(row, max_chars=1024)
    result = slimmed["metadata"]["result"]
    assert "data_base64" not in result
    body = json.loads(slimmed["content"])
    assert body["full_available"] is True


def test_apply_attachment_persist_strip_respects_flag() -> None:
    rows = [
        {
            "role": "tool",
            "message_type": "tool_result",
            "content": None,
            "metadata": {
                "tool_name": "read_attachment",
                "result": {"status": "ok", "content": "y" * 5000},
            },
        }
    ]
    disabled = MemoryConfig(
        attachment_pull=AttachmentPullConfig(persist_summary_only=False),
    )
    unchanged = _apply_attachment_persist_strip(rows, disabled)
    assert unchanged[0]["metadata"]["result"]["content"] == "y" * 5000

    enabled = MemoryConfig(attachment_pull=AttachmentPullConfig(persist_summary_only=True))
    stripped = _apply_attachment_persist_strip(rows, enabled)
    assert "content" not in stripped[0]["metadata"]["result"]


def test_attachment_pull_memory_projector_replay() -> None:
    memory_config = parse_memory_config({})
    memory_config = MemoryConfig(
        attachment_pull=AttachmentPullConfig(persist_summary_only=True),
        slim=memory_config.slim,
    )
    rows = [
        {
            "role": "assistant",
            "message_type": "tool_call",
            "content": None,
            "sequence": 1,
            "metadata": {
                "call_id": "c1",
                "tool_name": "read_attachment",
                "arguments": {"attachment_id": "doc-1"},
            },
        },
        {
            "role": "tool",
            "message_type": "tool_result",
            "content": None,
            "sequence": 2,
            "metadata": {
                "call_id": "c1",
                "tool_name": "read_attachment",
                "result": {
                    "status": "ok",
                    "attachment_id": "doc-1",
                    "content": "secret " * 5000,
                },
            },
        },
    ]
    projected = HistoryProjection().project_rows(rows, memory_config)
    assert projected[0]["metadata"]["arguments"]["_memory_preview"].startswith("read_attachment:")
    replay_content = projected[1].get("content") or ""
    assert len(replay_content) < 5000
    assert len(replay_content) <= 4097
    slim_result = projected[1]["metadata"]["result"]
    assert slim_result["persisted_summary"] is True
    assert "content" not in slim_result
    assert len(str(slim_result.get("summary") or "")) < 5000


def test_attachment_pull_projector_direct() -> None:
    projector = AttachmentPullMemoryProjector()
    cfg = parse_memory_config({}).slim
    result = projector.slim_result(
        tool_name="analyze_image",
        content=None,
        metadata={
            "tool_name": "analyze_image",
            "result": {
                "status": "ok",
                "attachment_id": "i1",
                "data_base64": "A" * 10_000,
            },
        },
        config=cfg,
    )
    assert "data_base64" not in result.metadata["result"]
    assert result.content

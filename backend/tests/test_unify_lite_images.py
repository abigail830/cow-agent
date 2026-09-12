import uuid

from agent_framework import Message

from app.platform.attachments.unify_lite.message_builder import build_user_run_input_lite
from app.platform.attachments.unify_lite.partition import partition_unify_lite_attachments
from app.platform.attachments.unify_lite.types import ExtractedAttachment
from app.platform.attachments.unify_lite.validation import is_unify_lite_file


class _Row:
    def __init__(self, *, filename: str, mime_type: str) -> None:
        self.id = uuid.uuid4()
        self.filename = filename
        self.mime_type = mime_type
        self.size_bytes = 128
        self.provider = "unify_lite"
        self.provider_file_id = "inline:test"
        self.chat_id = uuid.uuid4()


def test_is_unify_lite_file_accepts_images() -> None:
    assert is_unify_lite_file(filename="shot.png", mime_type="image/png")
    assert is_unify_lite_file(filename="notes.txt", mime_type="text/plain")


def test_partition_unify_lite_attachments() -> None:
    text_row = _Row(filename="notes.txt", mime_type="text/plain")
    image_row = _Row(filename="shot.png", mime_type="image/png")
    text_rows, image_rows = partition_unify_lite_attachments([text_row, image_row])
    assert text_rows == [text_row]
    assert image_rows == [image_row]


def test_build_user_run_input_lite_hybrid_message(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    image_row = _Row(filename="shot.png", mime_type="image/png")
    image_row.chat_id = chat_id
    image_row.id = attachment_id
    image_row.provider_file_id = f"inline:{attachment_id}"
    image_row.size_bytes = 4

    monkeypatch.setattr(
        "app.platform.attachments.native.maf_content.load_inline_attachment",
        lambda _chat_id, _attachment_id: b"\x89PNG\r\n",
    )

    extracted = [
        ExtractedAttachment(
            attachment_id=uuid.uuid4(),
            filename="notes.txt",
            mime_type="text/plain",
            content="hello doc",
        )
    ]
    run_input = build_user_run_input_lite(
        "explain @shot.png",
        extracted,
        image_attachments=[image_row],
        size_bytes_by_id={extracted[0].attachment_id: 10, image_row.id: 4},
    )

    assert isinstance(run_input, Message)
    assert run_input.role == "user"
    assert len(run_input.contents) == 2
    assert run_input.contents[0].type == "text"
    assert "Attachments — unify-lite" in (run_input.contents[0].text or "")
    assert run_input.contents[1].type == "data"
    assert run_input.contents[1].media_type == "image/png"

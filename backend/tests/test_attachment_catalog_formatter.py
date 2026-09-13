import uuid

from app.platform.attachments.catalog.formatter import format_catalog_block
from app.platform.attachments.run_state import AttachmentRecord


def test_catalog_block_sorted_by_attachment_id() -> None:
    first = AttachmentRecord(
        attachment_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        chat_id=uuid.uuid4(),
        filename="b.txt",
        mime_type="text/plain",
        provider="unify_lite",
        provider_file_id="inline:b",
        size_bytes=1,
        gist="beta",
    )
    second = AttachmentRecord(
        attachment_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        chat_id=uuid.uuid4(),
        filename="a.txt",
        mime_type="text/plain",
        provider="unify_lite",
        provider_file_id="inline:a",
        size_bytes=1,
        gist="alpha",
    )
    block = format_catalog_block([first, second])
    assert block.index("filename=a.txt") < block.index("filename=b.txt")

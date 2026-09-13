import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platform.attachments.modes import AttachmentProcessingMode
from app.platform.attachments.service import AttachmentService
from app.platform.attachments.unify_lite.handler import UnifyLiteAttachmentHandler
from app.platform.attachments.validation import validate_attachment_file
from app.config import Settings


@pytest.mark.asyncio
async def test_unify_lite_upload_dedupes_by_hash(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    data = b"same content bytes"
    existing_id = uuid.uuid4()

    existing_row = MagicMock()
    existing_row.id = existing_id
    existing_row.filename = "a.txt"
    existing_row.mime_type = "text/plain"
    existing_row.size_bytes = len(data)
    existing_row.provider = AttachmentProcessingMode.UNIFY_LITE.value
    existing_row.provider_file_id = f"inline:{existing_id}"

    repo = MagicMock()
    repo.find_by_content_hash = AsyncMock(return_value=existing_row)
    repo.insert = AsyncMock()

    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    handler = UnifyLiteAttachmentHandler(db, repo)
    monkeypatch.setattr(
        "app.platform.attachments.unify_lite.handler.save_inline_attachment",
        lambda *_args, **_kwargs: None,
    )

    result = await handler.upload(
        chat_id,
        filename="b.txt",
        mime_type="text/plain",
        data=data,
    )

    assert result["id"] == str(existing_id)
    repo.insert.assert_not_called()


@pytest.mark.asyncio
async def test_native_upload_no_hash_dedup(monkeypatch) -> None:
    """Native uploader always inserts — no content_hash dedup lookup."""
    from app.platform.attachments.native.upload import NativeAttachmentUploader

    chat_id = uuid.uuid4()
    repo = MagicMock()
    repo.find_by_content_hash = AsyncMock()
    repo.insert = AsyncMock()
    inserted = MagicMock()
    inserted.id = uuid.uuid4()
    inserted.filename = "a.png"
    inserted.mime_type = "image/png"
    inserted.size_bytes = 4
    inserted.provider = "dashscope"
    inserted.provider_file_id = "inline:test"
    repo.insert.return_value = inserted

    db = MagicMock()
    db.get = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    uploader = NativeAttachmentUploader(db, repo)
    monkeypatch.setattr(
        "app.platform.attachments.native.upload.resolve_chat_model",
        AsyncMock(return_value=MagicMock(provider="dashscope")),
    )
    monkeypatch.setattr(
        "app.platform.attachments.native.upload.save_inline_attachment",
        lambda *_args, **_kwargs: None,
    )

    await uploader.upload(chat_id, filename="a.png", mime_type="image/png", data=b"\x89PNG")
    repo.find_by_content_hash.assert_not_called()
    repo.insert.assert_called_once()


def test_validate_rejects_over_5mb_default() -> None:
    settings = Settings(
        ATTACHMENT_MAX_FILES_PER_MESSAGE=5,
        ATTACHMENT_MAX_BYTES_PER_FILE=5 * 1024 * 1024,
        ATTACHMENT_MAX_TOTAL_BYTES_PER_MESSAGE=50 * 1024 * 1024,
    )
    with pytest.raises(ValueError, match="5 MB"):
        validate_attachment_file(
            filename="big.txt",
            mime_type="text/plain",
            size_bytes=5 * 1024 * 1024 + 1,
            settings=settings,
        )

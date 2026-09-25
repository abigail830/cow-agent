"""Submit and track multi-file audio transcription captures."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from agent_framework import Content, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Chat, ChatAttachment, ChatUiAnnotation
from app.db.repositories.attachments import AttachmentRepository
from app.db.repositories.audio_captures import AudioCaptureRepository
from app.db.repositories.chat_messages import ChatMessageRepository
from app.db.repositories.chat_ui_annotations import ChatUiAnnotationRepository
from app.platform.blob.client import blob_exists, blob_storage_enabled
from app.platform.attachments.hash import sha256_hex
from app.platform.attachments.kinds import AttachmentKind, classify_attachment
from app.platform.attachments.storage import (
    format_inline_provider_file_id,
    inline_attachment_blob_path,
    save_inline_attachment,
)
from app.platform.audio_capture.asr_context import load_asr_context_for_chat
from app.platform.audio_capture.enqueue import enqueue_capture_parse_job
from app.platform.docstore.repository import DocstoreRepository


def _display_title(title: str | None, *, part_count: int) -> str:
    if title and title.strip():
        return title.strip()
    if part_count == 1:
        return "Audio transcript"
    return f"Audio transcript ({part_count} files)"


def _user_summary(*, part_filenames: list[str]) -> str:
    if len(part_filenames) == 1:
        return f"Transcribed audio file: {part_filenames[0]}"
    names = ", ".join(part_filenames)
    return f"Transcribed {len(part_filenames)} audio files: {names}"


def artifact_spec(
    *,
    capture_id: uuid.UUID,
    host_attachment_id: uuid.UUID,
    title: str,
    job_status: str,
    download_url: str | None = None,
    preview_url: str | None = None,
) -> dict[str, Any]:
    filename = f"{title}.md"
    return {
        "kind": "audio_transcript",
        "title": title,
        "format": "markdown",
        "content": "",
        "filename": filename,
        "artifact_id": str(host_attachment_id),
        "download_url": download_url,
        "preview_url": preview_url,
        "job_status": job_status,
        "attachment_id": str(host_attachment_id),
        "capture_id": str(capture_id),
        "source": "audio_capture",
    }


def _max_capture_total_bytes() -> int:
    return int(get_settings().audio_capture_max_total_bytes)


def _validate_audio_part(*, filename: str, mime_type: str, size_bytes: int) -> None:
    if size_bytes <= 0:
        raise ValueError(f"File is empty: {filename}")
    kind = classify_attachment(filename=filename, mime_type=mime_type)
    if kind != AttachmentKind.AUDIO:
        raise ValueError(f"Unsupported audio file: {filename}")


def _validate_capture_files(files: list[tuple[str, str, bytes]]) -> None:
    if not files:
        raise ValueError("At least one audio file is required")
    max_total = _max_capture_total_bytes()
    total = sum(len(data) for _, _, data in files)
    if total > max_total:
        raise ValueError(
            f"Audio capture exceeds {max_total / (1024 * 1024):.0f} MB total limit "
            f"(current {total / (1024 * 1024):.1f} MB)"
        )
    for filename, mime_type, data in files:
        _validate_audio_part(filename=filename, mime_type=mime_type, size_bytes=len(data))


def _validate_capture_part_specs(parts: list[dict[str, Any]]) -> None:
    if not parts:
        raise ValueError("At least one audio file is required")
    max_total = _max_capture_total_bytes()
    total = sum(int(part["size_bytes"]) for part in parts)
    if total > max_total:
        raise ValueError(
            f"Audio capture exceeds {max_total / (1024 * 1024):.0f} MB total limit "
            f"(current {total / (1024 * 1024):.1f} MB)"
        )
    for part in parts:
        _validate_audio_part(
            filename=str(part["filename"]),
            mime_type=str(part["mime_type"]),
            size_bytes=int(part["size_bytes"]),
        )


class AudioCaptureService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._attachments = AttachmentRepository(session)
        self._captures = AudioCaptureRepository(session)
        self._messages = ChatMessageRepository(session)
        self._annotations = ChatUiAnnotationRepository(session)

    async def submit_capture(
        self,
        chat: Chat,
        *,
        title: str | None,
        files: list[tuple[str, str, bytes]],
    ) -> dict[str, Any]:
        _validate_capture_files(files)
        chat_id = chat.id
        asr_context = await load_asr_context_for_chat(self._session, chat_id)
        display_title = _display_title(title, part_count=len(files))

        host_id = uuid.uuid4()
        host_row = await self._attachments.insert(
            chat_id=chat.id,
            provider="platform",
            provider_file_id=format_inline_provider_file_id(host_id),
            filename=f"{display_title}.md",
            mime_type="text/markdown",
            size_bytes=0,
            attachment_id=host_id,
            attachment_role="transcript_host",
            parse_status="ready",
        )

        capture = await self._captures.insert(
            chat_id=chat.id,
            host_attachment_id=host_row.id,
            title=display_title,
            context_snapshot={"asr_context": asr_context},
            status="running",
        )
        host_row.capture_id = capture.id

        part_specs: list[dict[str, Any]] = []
        part_filenames: list[str] = []
        for sort_order, (filename, mime_type, data) in enumerate(files):
            part_id = uuid.uuid4()
            await asyncio.to_thread(save_inline_attachment, chat.id, part_id, data)
            part_row = await self._attachments.insert(
                chat_id=chat.id,
                provider="platform",
                provider_file_id=format_inline_provider_file_id(part_id),
                filename=filename,
                mime_type=mime_type,
                size_bytes=len(data),
                content_hash=sha256_hex(data),
                attachment_id=part_id,
                attachment_role="audio_part",
                capture_id=capture.id,
                parse_status="skipped",
            )
            part_filenames.append(filename)
            part_specs.append(
                {
                    "attachment_id": str(part_row.id),
                    "sort_order": sort_order,
                    "filename": filename,
                    "mime_type": mime_type,
                    "size_bytes": len(data),
                }
            )

        capture.context_snapshot = {"asr_context": asr_context, "parts": part_specs}
        await self._session.flush()

        turn_id = uuid.uuid4()
        user_body = Message(
            role="user",
            contents=[Content.from_text(_user_summary(part_filenames=part_filenames))],
            additional_properties={
                "platform": {
                    "audio_capture_input": {
                        "capture_id": str(capture.id),
                        "title": display_title,
                        "part_count": len(part_specs),
                        "filenames": part_filenames,
                    }
                }
            },
        ).to_dict()
        user_message = await self._messages.insert(chat_id=chat.id, turn_id=turn_id, body=user_body)

        annotation = await self._annotations.insert(
            chat_id=chat.id,
            turn_id=turn_id,
            kind="artifact",
            ref=str(host_row.id),
            display={
                "spec": artifact_spec(
                    capture_id=capture.id,
                    host_attachment_id=host_row.id,
                    title=display_title,
                    job_status="running",
                )
            },
            anchor_message_id=user_message.id,
        )

        capture.input_message_id = user_message.id
        capture.output_annotation_id = annotation.id
        await self._session.flush()

        host_row = await enqueue_capture_parse_job(
            self._session,
            capture=capture,
            host_row=host_row,
        )
        capture.parse_job_id = host_row.parse_job_id
        await self._session.commit()
        return await self.get_capture(chat.id, capture.id)

    async def submit_capture_from_blob_parts(
        self,
        chat: Chat,
        *,
        title: str | None,
        parts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not blob_storage_enabled():
            raise ValueError("Blob storage is required for client upload submit")
        ordered = sorted(parts, key=lambda part: int(part["sort_order"]))
        _validate_capture_part_specs(ordered)

        chat_id = chat.id
        for part in ordered:
            attachment_id = uuid.UUID(str(part["attachment_id"]))
            pathname = inline_attachment_blob_path(chat_id, attachment_id)
            exists = await asyncio.to_thread(blob_exists, pathname)
            if not exists:
                raise ValueError(f"Uploaded file not found: {part['filename']}")

        asr_context = await load_asr_context_for_chat(self._session, chat_id)
        display_title = _display_title(title, part_count=len(ordered))

        host_id = uuid.uuid4()
        host_row = await self._attachments.insert(
            chat_id=chat.id,
            provider="platform",
            provider_file_id=format_inline_provider_file_id(host_id),
            filename=f"{display_title}.md",
            mime_type="text/markdown",
            size_bytes=0,
            attachment_id=host_id,
            attachment_role="transcript_host",
            parse_status="ready",
        )

        capture = await self._captures.insert(
            chat_id=chat.id,
            host_attachment_id=host_row.id,
            title=display_title,
            context_snapshot={"asr_context": asr_context},
            status="running",
        )
        host_row.capture_id = capture.id

        part_specs: list[dict[str, Any]] = []
        part_filenames: list[str] = []
        for part in ordered:
            attachment_id = uuid.UUID(str(part["attachment_id"]))
            filename = str(part["filename"])
            mime_type = str(part["mime_type"])
            size_bytes = int(part["size_bytes"])
            sort_order = int(part["sort_order"])
            part_row = await self._attachments.insert(
                chat_id=chat.id,
                provider="platform",
                provider_file_id=format_inline_provider_file_id(attachment_id),
                filename=filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                attachment_id=attachment_id,
                attachment_role="audio_part",
                capture_id=capture.id,
                parse_status="skipped",
            )
            part_filenames.append(filename)
            part_specs.append(
                {
                    "attachment_id": str(part_row.id),
                    "sort_order": sort_order,
                    "filename": filename,
                    "mime_type": mime_type,
                    "size_bytes": size_bytes,
                }
            )

        capture.context_snapshot = {"asr_context": asr_context, "parts": part_specs}
        await self._session.flush()

        turn_id = uuid.uuid4()
        user_body = Message(
            role="user",
            contents=[Content.from_text(_user_summary(part_filenames=part_filenames))],
            additional_properties={
                "platform": {
                    "audio_capture_input": {
                        "capture_id": str(capture.id),
                        "title": display_title,
                        "part_count": len(part_specs),
                        "filenames": part_filenames,
                    }
                }
            },
        ).to_dict()
        user_message = await self._messages.insert(chat_id=chat.id, turn_id=turn_id, body=user_body)

        annotation = await self._annotations.insert(
            chat_id=chat.id,
            turn_id=turn_id,
            kind="artifact",
            ref=str(host_row.id),
            display={
                "spec": artifact_spec(
                    capture_id=capture.id,
                    host_attachment_id=host_row.id,
                    title=display_title,
                    job_status="running",
                )
            },
            anchor_message_id=user_message.id,
        )

        capture.input_message_id = user_message.id
        capture.output_annotation_id = annotation.id
        await self._session.flush()

        host_row = await enqueue_capture_parse_job(
            self._session,
            capture=capture,
            host_row=host_row,
        )
        capture.parse_job_id = host_row.parse_job_id
        await self._session.commit()
        return await self.get_capture(chat.id, capture.id)

    async def get_capture(self, chat_id: uuid.UUID, capture_id: uuid.UUID) -> dict[str, Any]:
        capture = await self._captures.get_for_chat(chat_id, capture_id)
        if capture is None:
            raise ValueError("Capture not found")
        host = await self._attachments.get(capture.host_attachment_id)
        parts = await self._captures.list_parts(capture.id)
        return self._serialize_capture(capture, host=host, parts=parts)

    async def retry_capture(self, chat_id: uuid.UUID, capture_id: uuid.UUID) -> dict[str, Any]:
        capture = await self._captures.get_for_chat(chat_id, capture_id)
        if capture is None:
            raise ValueError("Capture not found")
        host = await self._attachments.get(capture.host_attachment_id)
        if host is None:
            raise ValueError("Capture host attachment missing")

        host_row = await enqueue_capture_parse_job(self._session, capture=capture, host_row=host)
        await self._captures.update_status(
            capture.id,
            status="running",
            parse_job_id=host_row.parse_job_id,
            error_code=None,
            error_message=None,
        )
        if capture.output_annotation_id:
            annotation = await self._session.get(ChatUiAnnotation, capture.output_annotation_id)
            if annotation is not None:
                spec = dict((annotation.display or {}).get("spec") or {})
                spec["job_status"] = "running"
                annotation.display = {**(annotation.display or {}), "spec": spec}
        await self._session.commit()
        return await self.get_capture(chat_id, capture_id)

    def _serialize_capture(
        self,
        capture,
        *,
        host: ChatAttachment | None,
        parts: list[ChatAttachment],
    ) -> dict[str, Any]:
        download_url = None
        preview_url = None
        if host is not None:
            base = f"/api/v1/chats/{capture.chat_id}/attachments/{host.id}"
            download_url = f"{base}/parsed/content.md"
            preview_url = download_url

        return {
            "id": str(capture.id),
            "chat_id": str(capture.chat_id),
            "title": capture.title,
            "status": capture.status,
            "parse_job_id": capture.parse_job_id,
            "host_attachment_id": str(capture.host_attachment_id),
            "input_message_id": str(capture.input_message_id) if capture.input_message_id else None,
            "output_annotation_id": str(capture.output_annotation_id) if capture.output_annotation_id else None,
            "error_code": capture.error_code,
            "error_message": capture.error_message,
            "context_snapshot": capture.context_snapshot,
            "created_at": capture.created_at.isoformat() if capture.created_at else None,
            "updated_at": capture.updated_at.isoformat() if capture.updated_at else None,
            "host_attachment": {
                "id": str(host.id),
                "parse_status": host.parse_status,
                "parse_stage_snapshot": host.parse_stage_snapshot,
            }
            if host
            else None,
            "parts": [
                {
                    "attachment_id": str(part.id),
                    "filename": part.filename,
                    "mime_type": part.mime_type,
                    "size_bytes": part.size_bytes,
                }
                for part in parts
            ],
            "download_url": download_url,
            "preview_url": preview_url,
        }

from __future__ import annotations

from app.platform.attachments.kinds import AttachmentKind, classify_attachment
from app.platform.doc_retrieval.store import is_document_kind
from app.platform.parse_pipeline.router import resolve_pipeline


def test_classify_audio_extensions() -> None:
    assert classify_attachment(filename="meeting.mp3", mime_type="audio/mpeg") == AttachmentKind.AUDIO
    assert classify_attachment(filename="clip.wav", mime_type="audio/wav") == AttachmentKind.AUDIO


def test_audio_pipeline_route() -> None:
    resolution = resolve_pipeline(AttachmentKind.AUDIO)
    assert resolution.action == "parse"
    assert resolution.pipeline_id == "audio_transcription_standard"


def test_audio_is_document_kind() -> None:
    assert is_document_kind(AttachmentKind.AUDIO.value)

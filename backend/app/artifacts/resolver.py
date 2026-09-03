"""Resolve artifact payloads from chat-artifacts or legacy proposal-artifacts."""

from __future__ import annotations

import uuid

from app.artifacts.storage import (
    ChatArtifactPayload,
    chat_artifact_exists,
    load_chat_artifact_payload,
    load_slide_preview_payload,
)
from app.proposal.storage import ArtifactPayload, load_artifact_payload as load_proposal_artifact_payload


def load_artifact_payload(
    chat_id: uuid.UUID,
    artifact_id: str,
    *,
    variant: str | None = None,
) -> ArtifactPayload | ChatArtifactPayload | None:
    if chat_artifact_exists(chat_id, artifact_id):
        return load_chat_artifact_payload(chat_id, artifact_id, variant=variant)
    return load_proposal_artifact_payload(chat_id, artifact_id, variant=variant)


def load_preview_payload(
    chat_id: uuid.UUID,
    artifact_id: str,
    file_path: str,
) -> ChatArtifactPayload | None:
    return load_slide_preview_payload(chat_id, artifact_id, file_path)

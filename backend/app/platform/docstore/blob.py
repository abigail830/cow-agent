"""Read/write parse artifacts alongside inline attachment storage."""

from __future__ import annotations

import uuid

from app.agent_specific.proposal.blob_client import blob_get, blob_put, blob_storage_enabled
from app.platform.docstore.paths import (
    blob_figure_object_name,
    blob_parsed_object_name,
    parsed_artifact_dir,
    parsed_artifact_path,
    parsed_figure_path,
)


def save_parsed_artifact(
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    artifact_key: str,
    data: bytes,
    *,
    content_type: str = "application/octet-stream",
) -> None:
    if blob_storage_enabled():
        blob_put(
            blob_parsed_object_name(chat_id, attachment_id, artifact_key),
            data,
            content_type=content_type,
        )
        return
    path = parsed_artifact_path(chat_id, attachment_id, artifact_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def load_parsed_artifact(chat_id: uuid.UUID, attachment_id: uuid.UUID, artifact_key: str) -> bytes:
    if blob_storage_enabled():
        raw = blob_get(blob_parsed_object_name(chat_id, attachment_id, artifact_key))
        if raw is None:
            raise FileNotFoundError(artifact_key)
        return raw
    path = parsed_artifact_path(chat_id, attachment_id, artifact_key)
    if not path.is_file():
        raise FileNotFoundError(artifact_key)
    return path.read_bytes()


def parsed_artifact_exists(chat_id: uuid.UUID, attachment_id: uuid.UUID, artifact_key: str) -> bool:
    try:
        load_parsed_artifact(chat_id, attachment_id, artifact_key)
        return True
    except FileNotFoundError:
        return False


def ensure_parsed_dir(chat_id: uuid.UUID, attachment_id: uuid.UUID) -> None:
    if not blob_storage_enabled():
        parsed_artifact_dir(chat_id, attachment_id).mkdir(parents=True, exist_ok=True)


def save_parsed_figure(
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    figure_id: str,
    extension: str,
    data: bytes,
    *,
    content_type: str = "application/octet-stream",
) -> None:
    if blob_storage_enabled():
        blob_put(
            blob_figure_object_name(chat_id, attachment_id, figure_id, extension),
            data,
            content_type=content_type,
        )
        return
    path = parsed_figure_path(chat_id, attachment_id, figure_id, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def load_parsed_figure(
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    figure_id: str,
    extension: str,
) -> bytes:
    if blob_storage_enabled():
        raw = blob_get(blob_figure_object_name(chat_id, attachment_id, figure_id, extension))
        if raw is None:
            raise FileNotFoundError(f"{figure_id}.{extension}")
        return raw
    path = parsed_figure_path(chat_id, attachment_id, figure_id, extension)
    if not path.is_file():
        raise FileNotFoundError(f"{figure_id}.{extension}")
    return path.read_bytes()

"""Last-mile image normalization for OpenAI-compatible vision requests."""

from __future__ import annotations

import base64
from typing import Any

def _normalize_data_url(url: str, *, filename: str) -> str:
    from app.platform.attachments.image_io import prepare_image_for_storage
    if not url.startswith("data:") or "," not in url:
        raise ValueError("图片引用格式无效，请重新上传。")
    header, b64 = url.split(",", 1)
    declared_mime = header.removeprefix("data:").split(";", 1)[0].strip() or None
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception as exc:
        raise ValueError("图片数据损坏，请重新上传。") from exc
    try:
        normalized, mime = prepare_image_for_storage(
            raw,
            filename=filename,
            mime_type=declared_mime,
        )
    except ValueError as exc:
        raise ValueError(
            "图片无法被模型识别（请确认是有效的 PNG/JPEG/GIF/WebP），请重新上传。"
        ) from exc
    encoded = base64.b64encode(normalized).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def _sanitize_image_part(part: dict[str, Any], *, filename: str) -> None:
    part_type = part.get("type")
    if part_type == "image_url":
        image_url = part.get("image_url")
        if not isinstance(image_url, dict):
            raise ValueError("图片引用格式无效，请重新上传。")
        url = str(image_url.get("url") or "")
        image_url["url"] = _normalize_data_url(url, filename=filename)
        return

    if part_type != "file":
        return

    file_obj = part.get("file")
    if isinstance(file_obj, dict):
        file_data = str(file_obj.get("file_data") or "")
        if file_data.startswith("data:"):
            file_obj["file_data"] = _normalize_data_url(
                file_data,
                filename=str(file_obj.get("filename") or filename),
            )
        return

    file_data = part.get("file_data")
    if isinstance(file_data, str) and file_data.startswith("data:"):
        part["file_data"] = _normalize_data_url(
            file_data,
            filename=str(part.get("filename") or filename),
        )


def sanitize_openai_image_payloads(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Re-encode inline images so vision APIs never receive stale/corrupt bytes."""
    for msg in messages:
        body = msg.get("content")
        if not isinstance(body, list):
            continue
        filename = "attachment.png"
        for part in body:
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"image_url", "file"}:
                _sanitize_image_part(part, filename=filename)
    return messages

"""Unauthenticated public endpoints (signed-token gated)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.platform.attachments.storage import load_inline_attachment
from app.platform.audio_capture.signed_urls import verify_asr_file_token

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/asr-files/{token}")
async def get_asr_file(token: str) -> Response:
    try:
        payload = verify_asr_file_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="invalid or expired token") from exc
    attachment_id = uuid.UUID(str(payload["attachment_id"]))
    scope = str(payload.get("document_scope") or "chat")
    try:
        if scope == "hub":
            from app.platform.document_hub.storage import load_hub_original

            user_id = uuid.UUID(str(payload["user_id"]))
            data = load_hub_original(user_id, attachment_id)
        else:
            chat_id = uuid.UUID(str(payload["chat_id"]))
            data = load_inline_attachment(chat_id, attachment_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="invalid token payload") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc
    return Response(content=data, media_type="application/octet-stream")

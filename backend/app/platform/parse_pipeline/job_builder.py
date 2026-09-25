from __future__ import annotations

import secrets
import uuid
from typing import Any
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from app.config import get_settings
from app.db.models import ChatAttachment
from app.platform.docstore.storage_spec import build_file_storage_spec, build_internal_storage_spec


def _new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:26]}"


def _new_run_token() -> str:
    return f"run_{secrets.token_urlsafe(32)}"


def _new_webhook_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(24)}"


def hash_run_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def build_job_payload(
    row: ChatAttachment,
    *,
    pipeline_id: str,
    job_id: str,
    webhook_secret: str,
    use_internal_http: bool,
    source_extra: dict | None = None,
    options_extra: dict | None = None,
) -> tuple[dict, str]:
    settings = get_settings()
    run_token = _new_run_token()
    public_base = (settings.parse_pipeline_public_base_url or "").strip()

    if use_internal_http:
        if not public_base:
            raise ValueError("PARSE_PIPELINE_PUBLIC_BASE_URL is required for HTTP storage")
        storage = build_internal_storage_spec(
            public_base_url=public_base,
            attachment_id=row.id,
            filename=row.filename,
            mime_type=row.mime_type,
            size_bytes=row.size_bytes,
            content_hash=row.content_hash,
            run_token=run_token,
        )
        webhook_url = f"{public_base.rstrip('/')}{settings.parse_pipeline_webhook_path}"
    else:
        storage = build_file_storage_spec(
            chat_id=row.chat_id,
            attachment_id=row.id,
            filename=row.filename,
            mime_type=row.mime_type,
            size_bytes=row.size_bytes,
            content_hash=row.content_hash,
        )
        webhook_url = None

    idempotency_key = None
    if row.content_hash:
        idempotency_key = f"sha256:{row.chat_id}:{row.id}:{row.content_hash}"

    payload = {
        "schema_version": "1.0",
        "job_id": job_id,
        "idempotency_key": idempotency_key,
        "pipeline_id": pipeline_id,
        "storage": storage,
        "source": {
            "source_type": "chat_attachment",
            "source_id": str(row.id),
            "tenant_id": str(row.chat_id),
            "filename": row.filename,
            "mime_type": row.mime_type,
            "size_bytes": row.size_bytes,
            "content_hash": row.content_hash,
            **(source_extra or {}),
        },
        "options": {
            "office": {
                "markitdown_enabled": settings.office_markitdown_enabled,
            },
            "document_mind": {
                "llm_enhancement": True,
                "enhancement_mode": "VLM",
                "output_formats": ["markdown", "visualLayoutInfo"],
            },
            **(options_extra or {}),
        },
        "callbacks": {
            "webhook_url": webhook_url,
            "webhook_secret": webhook_secret,
            "events": ["stage.updated", "job.completed", "job.failed"],
        },
    }
    return payload, run_token


def run_expires_at() -> datetime:
    settings = get_settings()
    ttl = max(300, int(settings.parse_pipeline_run_token_ttl_sec))
    return datetime.now(timezone.utc) + timedelta(seconds=ttl)


def new_job_id() -> str:
    return _new_job_id()


def new_webhook_secret() -> str:
    return _new_webhook_secret()


def build_capture_job_payload(
    host_row: ChatAttachment,
    *,
    capture_id: uuid.UUID,
    parts: list[dict],
    pipeline_id: str,
    asr_context: str | None,
    job_id: str | None = None,
    webhook_secret: str | None = None,
    use_internal_http: bool = True,
) -> tuple[dict, str]:
    settings = get_settings()
    resolved_job_id = job_id or _new_job_id()
    resolved_webhook_secret = webhook_secret or _new_webhook_secret()
    source_extra = {
        "capture": {
            "capture_id": str(capture_id),
            "parts": parts,
        }
    }
    options_extra = {
        "asr": {
            "provider": settings.asr_provider,
            "fallback_provider": settings.asr_fallback_provider,
            "context_text": asr_context,
            "enable_words": False,
        }
    }
    payload, run_token = build_job_payload(
        host_row,
        pipeline_id=pipeline_id,
        job_id=resolved_job_id,
        webhook_secret=resolved_webhook_secret,
        use_internal_http=use_internal_http,
        source_extra=source_extra,
        options_extra=options_extra,
    )
    return payload, run_token

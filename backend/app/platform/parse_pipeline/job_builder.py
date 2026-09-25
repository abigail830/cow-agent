from __future__ import annotations

import secrets
import uuid
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
    use_file_urls: bool,
) -> tuple[dict, str]:
    settings = get_settings()
    run_token = _new_run_token()
    public_base = (settings.parse_pipeline_public_base_url or "").strip()

    if use_file_urls or not public_base:
        storage = build_file_storage_spec(
            chat_id=row.chat_id,
            attachment_id=row.id,
            filename=row.filename,
            mime_type=row.mime_type,
            size_bytes=row.size_bytes,
            content_hash=row.content_hash,
        )
    else:
        storage = build_internal_storage_spec(
            public_base_url=public_base,
            attachment_id=row.id,
            filename=row.filename,
            mime_type=row.mime_type,
            size_bytes=row.size_bytes,
            content_hash=row.content_hash,
            run_token=run_token,
        )

    webhook_url = None
    if public_base:
        webhook_url = f"{public_base.rstrip('/')}{settings.parse_pipeline_webhook_path}"

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
        },
        "options": {
            "office": {
                "markitdown_enabled": settings.office_markitdown_enabled,
            },
            "document_mind": {
                "llm_enhancement": True,
                "enhancement_mode": "VLM",
                "output_formats": ["markdown", "visualLayoutInfo"],
            }
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

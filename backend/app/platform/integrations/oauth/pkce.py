"""OAuth 2.1 PKCE helpers and signed state (stateless, multi-replica safe)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

STATE_VERSION = "v1"
PENDING_TTL_SECONDS = 10 * 60


@dataclass(frozen=True)
class OAuthPendingState:
    user_id: str
    provider: str
    code_verifier: str
    created_at: int


def generate_code_verifier() -> str:
    return secrets.token_urlsafe(32)


def generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _sign_payload(encoded_payload: str, signing_key: str) -> str:
    digest = hmac.new(signing_key.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_oauth_state(*, user_id: str, provider: str, code_verifier: str, signing_key: str) -> str:
    payload: dict[str, Any] = {
        "user_id": user_id.strip(),
        "provider": provider.strip(),
        "code_verifier": code_verifier,
        "created_at": int(time.time()),
        "nonce": secrets.token_urlsafe(16),
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")
    signature = _sign_payload(encoded, signing_key)
    return f"{STATE_VERSION}.{encoded}.{signature}"


def consume_oauth_state(state: str, *, signing_key: str) -> OAuthPendingState | None:
    parts = state.strip().split(".")
    if len(parts) != 3 or parts[0] != STATE_VERSION:
        return None

    encoded, signature = parts[1], parts[2]
    expected = _sign_payload(encoded, signing_key)
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        raw = base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")
        parsed = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return None

    user_id = parsed.get("user_id")
    provider = parsed.get("provider")
    code_verifier = parsed.get("code_verifier")
    created_at = parsed.get("created_at")
    if not all(isinstance(value, str) for value in (user_id, provider, code_verifier)):
        return None
    if not isinstance(created_at, int):
        return None
    if int(time.time()) - created_at > PENDING_TTL_SECONDS:
        return None

    return OAuthPendingState(
        user_id=user_id,
        provider=provider,
        code_verifier=code_verifier,
        created_at=created_at,
    )

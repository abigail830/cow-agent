import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class SecretStoreError(Exception):
    pass


def _fernet() -> Fernet:
    key = get_settings().mcp_secrets_key
    if not key:
        raise SecretStoreError(
            "MCP_SECRETS_KEY is not configured. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secrets(payload: dict[str, Any]) -> str:
    """Encrypt a secrets dict for storage in mcp_servers.connection."""
    token = _fernet().encrypt(json.dumps(payload).encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secrets(token: str) -> dict[str, Any]:
    """Decrypt secrets_encrypted field from mcp_servers.connection."""
    try:
        raw = _fernet().decrypt(token.encode("utf-8"))
    except InvalidToken as exc:
        raise SecretStoreError("Failed to decrypt MCP secrets (wrong MCP_SECRETS_KEY?)") from exc
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise SecretStoreError("Decrypted MCP secrets must be a JSON object")
    return data

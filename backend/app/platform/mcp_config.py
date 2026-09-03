import copy
import re
from typing import Any

from app.platform.secret_store import SecretStoreError, decrypt_secrets, encrypt_secrets

REDACTED = "********"
SCHEMA_VERSION = 2

_URL_ARG_RE = re.compile(r"^(mysql|postgresql|postgres)://", re.I)


def _is_secret_arg(value: str) -> bool:
    return bool(_URL_ARG_RE.match(value.strip()))


def infer_transport(config: dict[str, Any]) -> str:
    if config.get("url"):
        return "http"
    if config.get("command"):
        return "stdio"
    return "stdio"


def _extract_secrets(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split Cursor-style MCP config into public preview + secrets payload."""
    public = copy.deepcopy(config)
    secrets: dict[str, Any] = {"env": {}, "headers": {}, "args": {}}

    if env := public.pop("env", None):
        if isinstance(env, dict):
            public_env: dict[str, str] = {}
            for k, v in env.items():
                sv = str(v)
                if not _is_redacted(v):
                    secrets["env"][str(k)] = sv
                public_env[str(k)] = REDACTED
            public["env"] = public_env

    if headers := public.pop("headers", None):
        if isinstance(headers, dict):
            public_headers: dict[str, str] = {}
            for k, v in headers.items():
                sv = str(v)
                if not _is_redacted(v):
                    secrets["headers"][str(k)] = sv
                public_headers[str(k)] = REDACTED
            public["headers"] = public_headers

    if args := public.get("args"):
        if isinstance(args, list):
            masked_args: list[str] = []
            for i, arg in enumerate(args):
                s = str(arg)
                if _is_secret_arg(s):
                    secrets["args"][str(i)] = s
                    masked_args.append(REDACTED)
                else:
                    masked_args.append(s)
            public["args"] = masked_args

    has_secrets = bool(secrets["env"] or secrets["headers"] or secrets["args"])
    return public, secrets if has_secrets else {}


def _merge_secrets_into_config(public: dict[str, Any], secrets: dict[str, Any]) -> dict[str, Any]:
    runtime = copy.deepcopy(public)
    if env := secrets.get("env"):
        runtime["env"] = dict(env)
    if headers := secrets.get("headers"):
        runtime["headers"] = dict(headers)
    if args := runtime.get("args"):
        if isinstance(args, list) and (secret_args := secrets.get("args")):
            runtime_args = list(args)
            for idx, value in secret_args.items():
                runtime_args[int(idx)] = value
            runtime["args"] = runtime_args
    return runtime


def _is_redacted(value: Any) -> bool:
    return isinstance(value, str) and value.strip() == REDACTED


def _merge_secret_dict(
    existing: dict[str, str],
    incoming: dict[str, Any] | None,
) -> dict[str, str]:
    if not incoming:
        return existing
    merged = dict(existing)
    for key, value in incoming.items():
        if value is None or _is_redacted(value) or (isinstance(value, str) and not value.strip()):
            continue
        merged[str(key)] = str(value)
    return merged


def _merge_secret_args(
    existing: dict[str, str],
    incoming_args: list[Any] | None,
) -> dict[str, str]:
    if not incoming_args:
        return existing
    merged = dict(existing)
    for i, arg in enumerate(incoming_args):
        s = str(arg)
        if _is_secret_arg(s):
            if not _is_redacted(s) and s.strip():
                merged[str(i)] = s
    return merged


def pack_for_storage(config: dict[str, Any]) -> dict[str, Any]:
    """Validate and store a Cursor-style MCP config with encrypted secrets."""
    if not config:
        raise ValueError("MCP config cannot be empty")
    if not config.get("url") and not config.get("command"):
        raise ValueError("MCP config requires either 'command' (stdio) or 'url' (http)")

    public, secrets = _extract_secrets(config)
    stored: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "config": public,
        "transport": infer_transport(config),
    }
    if secrets:
        stored["secrets_encrypted"] = encrypt_secrets(secrets)
    return stored


def merge_config_update(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Apply config update; redacted secret placeholders keep existing values."""
    legacy = _normalize_legacy(existing)
    existing_public = legacy.get("config") or {}
    existing_secrets: dict[str, Any] = {"env": {}, "headers": {}, "args": {}}
    if encrypted := legacy.get("secrets_encrypted"):
        existing_secrets = decrypt_secrets(encrypted)

    public, incoming_secrets = _extract_secrets(incoming)

    merged_secrets = {
        "env": _merge_secret_dict(existing_secrets.get("env") or {}, incoming.get("env")),
        "headers": _merge_secret_dict(existing_secrets.get("headers") or {}, incoming.get("headers")),
        "args": _merge_secret_args(existing_secrets.get("args") or {}, incoming.get("args")),
    }
    # Also accept freshly submitted plaintext secrets from incoming_secrets extraction
    for bucket in ("env", "headers", "args"):
        if bucket in incoming_secrets and incoming_secrets[bucket]:
            if bucket == "args":
                merged_secrets["args"] = {**merged_secrets.get("args", {}), **incoming_secrets["args"]}
            else:
                merged_secrets[bucket] = _merge_secret_dict(
                    merged_secrets.get(bucket) or {},
                    incoming_secrets[bucket],
                )

    stored: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "config": public,
        "transport": infer_transport({**public, **_merge_secrets_into_config(public, merged_secrets)}),
    }
    has_secrets = any(merged_secrets.get(k) for k in ("env", "headers", "args"))
    if has_secrets:
        stored["secrets_encrypted"] = encrypt_secrets(merged_secrets)
    return stored


def public_view(stored: dict[str, Any]) -> dict[str, Any]:
    """Masked config for API responses."""
    normalized = _normalize_legacy(stored)
    return {
        "transport": normalized.get("transport") or infer_transport(normalized.get("config") or {}),
        "config": normalized.get("config") or {},
        "secrets_configured": bool(normalized.get("secrets_encrypted")),
    }


def _normalize_legacy(stored: dict[str, Any]) -> dict[str, Any]:
    """Upgrade v1 postgres/custom records to v2 shape."""
    if stored.get("schema_version") == SCHEMA_VERSION and "config" in stored:
        return stored

    # Legacy postgres: args_prefix + secrets_encrypted(connection_url)
    if stored.get("server_type") == "postgres" or (
        stored.get("args_prefix") and stored.get("secrets_encrypted")
    ):
        public = {
            "command": stored.get("command", "npx"),
            "args": list(stored.get("args_prefix") or []),
        }
        if public["args"] and stored.get("secrets_encrypted"):
            public["args"].append(REDACTED)
        return {
            "schema_version": SCHEMA_VERSION,
            "transport": "stdio",
            "config": public,
            "secrets_encrypted": stored.get("secrets_encrypted"),
            "_legacy_args_key": "connection_url",
        }

    # Legacy custom stdio
    if stored.get("command"):
        return {
            "schema_version": SCHEMA_VERSION,
            "transport": "stdio",
            "config": {
                "command": stored["command"],
                "args": list(stored.get("args") or stored.get("args_prefix") or []),
            },
            "secrets_encrypted": stored.get("secrets_encrypted"),
        }

    if stored.get("config"):
        return stored

    raise SecretStoreError("Unsupported MCP connection format")


def legacy_secret_args_resolver(stored: dict[str, Any], secrets: dict[str, Any], public: dict[str, Any]) -> dict[str, Any]:
    """Map legacy connection_url secret to final arg."""
    if stored.get("_legacy_args_key") == "connection_url":
        url = secrets.get("connection_url")
        if url:
            runtime = copy.deepcopy(public)
            args = list(runtime.get("args") or [])
            if args and args[-1] == REDACTED:
                args[-1] = url
            else:
                args.append(url)
            runtime["args"] = args
            return runtime
    return _merge_secrets_into_config(public, secrets)


def resolve_runtime_config_safe(stored: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_legacy(stored)
    public = normalized.get("config") or {}
    if encrypted := normalized.get("secrets_encrypted"):
        secrets = decrypt_secrets(encrypted)
        if normalized.get("_legacy_args_key"):
            return legacy_secret_args_resolver(normalized, secrets, public)
        return _merge_secrets_into_config(public, secrets)
    return copy.deepcopy(public)

"""Parse profile.yaml hooks section into ordered (name, params) pairs."""

from __future__ import annotations

from typing import Any

from app.platform.hook_catalog import merge_hook_params

# Legacy: guardrails.sql keys mapped to hook params (deprecated; use hooks.<name> instead)
_LEGACY_SQL_PARAM_MAP: dict[str, dict[str, str]] = {
    "sql_validator": {"max_rows": "max_rows"},
    "result_truncator": {"max_observation_bytes": "max_observation_bytes"},
}


def _params_from_legacy_guardrails(hook_name: str, guardrails: dict[str, Any] | None) -> dict[str, Any]:
    sql = (guardrails or {}).get("sql") or {}
    mapping = _LEGACY_SQL_PARAM_MAP.get(hook_name, {})
    return {param: sql[src] for param, src in mapping.items() if src in sql}


def normalize_hooks(
    hooks_raw: Any,
    *,
    legacy_guardrails: dict[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Normalize hooks config to ordered (hook_name, merged_params).

    Supported profile shapes:

    .. code-block:: yaml

        # recommended — params live on each hook
        hooks:
          sql_validator:
            max_rows: 2000
          result_truncator:
            max_observation_bytes: 50000

        # minimal — platform defaults
        hooks:
          sql_validator: {}
          result_truncator: {}

        # list — defaults only
        hooks:
          - sql_validator
          - result_truncator

        # legacy (still supported)
        hooks:
          custom: [sql_validator, result_truncator]
        guardrails:
          sql: {max_rows: 2000}
    """
    if not hooks_raw:
        return []

    ordered: list[tuple[str, dict[str, Any]]] = []

    if isinstance(hooks_raw, list):
        for item in hooks_raw:
            if isinstance(item, str):
                name = item.strip()
                if name:
                    ordered.append((name, merge_hook_params(name, {})))
            elif isinstance(item, dict) and len(item) == 1:
                name, params = next(iter(item.items()))
                ordered.append((str(name), merge_hook_params(str(name), params or {})))
        return ordered

    if not isinstance(hooks_raw, dict):
        return []

    if "custom" in hooks_raw:
        for name in hooks_raw.get("custom") or []:
            hook_name = str(name).strip()
            if not hook_name:
                continue
            overrides = _params_from_legacy_guardrails(hook_name, legacy_guardrails)
            ordered.append((hook_name, merge_hook_params(hook_name, overrides)))
        return ordered

    for name, params in hooks_raw.items():
        hook_name = str(name).strip()
        if not hook_name:
            continue
        override = params if isinstance(params, dict) else {}
        ordered.append((hook_name, merge_hook_params(hook_name, override)))

    return ordered

"""Proxy OpenKMS knowledge-base list using the user's hybrid-search API key."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_MCP_SUFFIX = "/api/mcp/hybrid-search"


def resolve_hybrid_search_api_base(settings: Settings | None = None) -> str | None:
    cfg = settings or get_settings()
    explicit = (cfg.hybrid_search_api_base or "").strip().rstrip("/")
    if explicit:
        return explicit
    mcp = (cfg.hybrid_search_mcp_url or "").strip().rstrip("/")
    if not mcp:
        return None
    if mcp.endswith(_MCP_SUFFIX):
        return mcp[: -len(_MCP_SUFFIX)].rstrip("/") or None
    parsed = urlparse(mcp)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return None


class HybridSearchKbClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


async def list_visible_knowledge_bases(*, api_key: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    base = resolve_hybrid_search_api_base(settings)
    if not base:
        raise HybridSearchKbClientError("Hybrid Search API base URL is not configured")

    url = f"{base}/api/knowledge/knowledge-bases"
    timeout = float((settings or get_settings()).mcp_http_request_timeout)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key.strip()}"},
            )
    except httpx.HTTPError as exc:
        logger.warning("Failed to list knowledge bases from %s: %s", url, exc)
        raise HybridSearchKbClientError(f"Failed to reach knowledge-base API: {exc}") from exc

    if response.status_code == 401:
        raise HybridSearchKbClientError("Hybrid Search API key is invalid", status_code=401)
    if response.status_code == 403:
        raise HybridSearchKbClientError("Hybrid Search API key cannot list knowledge bases", status_code=403)
    if response.status_code >= 400:
        raise HybridSearchKbClientError(
            f"Knowledge-base API returned HTTP {response.status_code}",
            status_code=response.status_code,
        )

    payload = response.json()
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []

    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kb_id = str(item.get("id") or "").strip()
        if not kb_id:
            continue
        out.append(
            {
                "id": kb_id,
                "name": str(item.get("name") or kb_id),
                "description": item.get("description"),
                "type": item.get("type"),
                "item_count": item.get("item_count"),
                "is_configured": item.get("is_configured"),
            }
        )
    return out

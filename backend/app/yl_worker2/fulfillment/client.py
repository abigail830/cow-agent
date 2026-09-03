"""HTTP client for fulfillment center branch-replenishment API."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


class FulfillmentApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FulfillmentClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        settings = get_settings()
        self._base = (base_url or settings.fulfillment_api_base_url or "").rstrip("/")
        self._api_key = api_key if api_key is not None else settings.fulfillment_api_key
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def get_filter_options(self) -> dict[str, Any]:
        return await self._get("/meta/filters/fulfillment")

    async def create_branch_replenishment(self, body: dict[str, Any]) -> dict[str, Any]:
        data = await self._post("/fulfillment/branch-replenishment", body)
        item = data.get("item")
        if not isinstance(item, dict):
            raise FulfillmentApiError("create_branch_replenishment: missing item in response")
        return item

    async def generate_transfer(self, ids: list[str]) -> dict[str, Any]:
        if not ids:
            raise FulfillmentApiError("ids must not be empty", status_code=400)
        return await self._post(
            "/fulfillment/branch-replenishment/generate-transfer",
            {"ids": ids},
        )

    async def invalidate(self, ids: list[str]) -> dict[str, Any]:
        if not ids:
            raise FulfillmentApiError("ids must not be empty", status_code=400)
        return await self._post(
            "/fulfillment/branch-replenishment/invalidate",
            {"ids": ids},
        )

    async def confirm_branch_replenishment(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create draft then generate-transfer (single-form confirm)."""
        item = await self.create_branch_replenishment(body)
        form_id = str(item.get("id") or "")
        if not form_id:
            raise FulfillmentApiError("create response missing id")
        result = await self.generate_transfer([form_id])
        items = result.get("items") or []
        if items and isinstance(items[0], dict):
            return items[0]
        return item

    async def _get(self, path: str) -> dict[str, Any]:
        if not self._base:
            raise FulfillmentApiError("FULFILLMENT_API_BASE_URL is not configured")
        url = f"{self._base}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=self._headers())
        return self._parse_response(resp)

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if not self._base:
            raise FulfillmentApiError("FULFILLMENT_API_BASE_URL is not configured")
        url = f"{self._base}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=self._headers(), json=body)
        return self._parse_response(resp)

    @staticmethod
    def _parse_response(resp: httpx.Response) -> dict[str, Any]:
        try:
            data = resp.json()
        except Exception as exc:
            raise FulfillmentApiError(
                f"Invalid JSON response ({resp.status_code})",
                status_code=resp.status_code,
            ) from exc
        if resp.status_code >= 400:
            err = data.get("error") if isinstance(data, dict) else str(data)
            raise FulfillmentApiError(str(err or resp.text), status_code=resp.status_code)
        if not isinstance(data, dict):
            raise FulfillmentApiError("Unexpected response shape", status_code=resp.status_code)
        return data

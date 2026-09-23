from __future__ import annotations

from fastapi import Header, HTTPException, status

from parse_pipeline.config import get_settings


async def require_service_auth(
    authorization: str | None = Header(default=None),
    x_parse_caller_id: str | None = Header(default=None, alias="X-Parse-Caller-Id"),
) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    key_map = get_settings().api_key_map()
    caller_id = key_map.get(token)
    if caller_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")
    if x_parse_caller_id and x_parse_caller_id != caller_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="caller_id mismatch")
    return caller_id

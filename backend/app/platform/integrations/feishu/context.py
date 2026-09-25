"""Per-run Feishu user access token context."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class FeishuContext:
    access_token: str | None
    account_label: str | None = None
    api_base: str = "https://open.feishu.cn"


_feishu_ctx: ContextVar[FeishuContext | None] = ContextVar("feishu_ctx", default=None)


def init_feishu_context(
    *,
    access_token: str | None,
    account_label: str | None = None,
    api_base: str = "https://open.feishu.cn",
) -> FeishuContext:
    ctx = FeishuContext(
        access_token=access_token,
        account_label=account_label,
        api_base=api_base.rstrip("/"),
    )
    _feishu_ctx.set(ctx)
    return ctx


def get_feishu_context() -> FeishuContext | None:
    return _feishu_ctx.get()


def require_feishu_context() -> FeishuContext:
    ctx = get_feishu_context()
    if ctx is None:
        raise RuntimeError("Feishu context not initialized for this run")
    return ctx


def reset_feishu_context() -> None:
    _feishu_ctx.set(None)

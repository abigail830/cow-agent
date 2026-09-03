"""Sandbox provider factory."""

from __future__ import annotations

from app.config import get_settings
from app.sandbox.protocol import SandboxProvider
from app.sandbox.providers.e2b import E2BSandboxProvider
from app.sandbox.providers.local import LocalSandboxProvider
from app.sandbox.providers.vercel import VercelSandboxProvider


def get_sandbox_provider() -> SandboxProvider:
    settings = get_settings()
    provider = (settings.sandbox_provider or "e2b").strip().lower()
    if provider == "local":
        return LocalSandboxProvider()
    if provider == "e2b":
        return E2BSandboxProvider(
            api_key=settings.e2b_api_key,
            timeout_seconds=settings.sandbox_timeout_seconds,
            export_pdf=settings.sandbox_slidev_export_pdf,
            template=settings.e2b_slidev_template,
            reuse_session=settings.sandbox_reuse_session,
        )
    if provider == "vercel":
        return VercelSandboxProvider()
    raise ValueError(f"Unsupported SANDBOX_PROVIDER: {provider}")

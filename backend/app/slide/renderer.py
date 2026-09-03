"""Slidev build orchestration."""

from __future__ import annotations

import re

from app.config import get_settings
from app.sandbox.factory import get_sandbox_provider
from app.sandbox.types import SlidevBuildOutput
from app.slide.build_cache import get_cached_build, put_cached_build, slide_build_cache_key
from app.slide.source_normalize import normalize_slidev_source

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify_title(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug[:48] or "slides"


class SlideRenderer:
    def build(self, slides_md: str, *, export_pdf: bool | None = None) -> SlidevBuildOutput:
        source = normalize_slidev_source((slides_md or "").strip())
        if not source:
            return SlidevBuildOutput(error="Slidev source is empty.")

        settings = get_settings()
        if export_pdf is None:
            export_pdf = settings.sandbox_slidev_export_pdf

        provider = get_sandbox_provider()
        cache_key = slide_build_cache_key(
            source,
            export_pdf=export_pdf,
            provider=provider.name,
            template=(settings.e2b_slidev_template or "").strip() or None,
        )
        cached = get_cached_build(cache_key)
        if cached is not None:
            return cached

        exports = ["spa"]
        if export_pdf:
            exports.append("pdf")
        output = provider.build_slidev(slides_md=source, exports=exports)
        if output.ok:
            put_cached_build(cache_key, output)
        return output

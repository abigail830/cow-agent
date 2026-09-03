"""Run Slidev builds off the asyncio event loop."""

from __future__ import annotations

import concurrent.futures
import contextvars
import logging

from app.config import get_settings
from app.sandbox.types import SlidevBuildOutput
from app.slide.renderer import SlideRenderer

logger = logging.getLogger(__name__)

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="slidev-build")


def run_slidev_build(slides_md: str) -> SlidevBuildOutput:
    """Execute Slidev build in a worker thread (E2B/npm can take minutes)."""
    settings = get_settings()
    timeout = max(60.0, settings.sandbox_timeout_seconds + 30.0)
    ctx = contextvars.copy_context()
    future = _executor.submit(ctx.run, SlideRenderer().build, slides_md)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.warning("Slidev build timed out after %.0fs", timeout)
        return SlidevBuildOutput(error=f"Slidev build timed out after {int(timeout)}s.")
    except Exception as exc:
        logger.exception("Slidev build worker failed")
        return SlidevBuildOutput(error=str(exc).strip() or "Slidev build failed.")

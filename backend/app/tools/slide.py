"""Slide deck rendering tools."""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool

from app.artifacts.context import get_run_artifact_state
from app.config import get_settings
from app.slide.source_normalize import normalize_slidev_source
from app.slide.artifact_builder import (
    build_html_ppt_artifact_spec,
    build_slide_artifact_spec,
    slide_tool_payload,
)
from app.slide.build_executor import run_slidev_build
from app.slide.build_jobs import submit_slide_build_job
from app.slide.html_ppt import build_html_ppt_dist

_LOG_TAIL_CHARS = 4000


def _queue_artifact(spec) -> dict[str, Any]:
    ctx = get_run_artifact_state()
    if ctx is None:
        return {"status": "error", "message": "Artifact context unavailable for this run."}
    queued = ctx.queue_artifact(spec)
    payload = spec.model_dump(mode="json")
    payload["status"] = "queued" if queued else "deduplicated"
    payload["queued"] = queued
    return payload


@tool(
    name="render_slidev",
    description=(
        "Build a Slidev presentation from Markdown source and show it in chat. "
        "Always call this after drafting or editing slides.md — do not ask the user "
        "to build elsewhere. On error, read the message/logs, fix the Markdown, and retry."
    ),
)
def render_slidev_tool(
    source: Annotated[str, "Complete Slidev Markdown (headmatter + --- slide separators)."],
    title: Annotated[str, "Short deck title for the artifact card."] = "Slide deck",
) -> dict[str, Any]:
    ctx = get_run_artifact_state()
    if ctx is None:
        return {"status": "error", "message": "Artifact context unavailable for this run."}

    normalized = normalize_slidev_source((source or "").strip())
    if not normalized:
        return {
            "status": "error",
            "message": "Slidev source is empty.",
            "hint": "Provide slides.md content with --- separators between slides.",
        }

    ctx.last_source = normalized
    settings = get_settings()

    if settings.sandbox_async_build:
        if ctx.chat_id is None:
            return {"status": "error", "message": "Chat context unavailable for async slide build."}
        job_id = submit_slide_build_job(
            chat_id=ctx.chat_id,
            slides_md=normalized,
            title=title,
        )
        return {
            "status": "building",
            "job_id": job_id,
            "message": (
                "Slide build started in the background. The preview will appear in chat "
                "when the build finishes; you may continue refining the deck."
            ),
        }

    build = run_slidev_build(normalized)
    if build.error:
        log_tail = (build.logs or "")[-_LOG_TAIL_CHARS:]
        return {
            "status": "error",
            "message": build.error,
            "logs": log_tail,
            "hint": "Fix Slidev syntax or frontmatter, then call render_slidev again.",
        }

    try:
        spec = build_slide_artifact_spec(
            title=title,
            source=normalized,
            chat_id=ctx.chat_id,
            dist_files=build.dist_files,
            pdf_bytes=build.pdf_bytes,
        )
    except OSError as exc:
        return {
            "status": "error",
            "message": str(exc).strip() or "Failed to persist slide artifact.",
            "hint": "Check ARTIFACT_STORAGE and BLOB_READ_WRITE_TOKEN.",
        }
    except RuntimeError as exc:
        return {
            "status": "error",
            "message": str(exc).strip() or "Failed to persist slide artifact.",
            "hint": "Check ARTIFACT_STORAGE and BLOB_READ_WRITE_TOKEN.",
        }

    payload = _queue_artifact(spec)
    payload.update(
        slide_tool_payload(
            spec,
            build_logs=(build.logs or "")[-_LOG_TAIL_CHARS:],
            warning=(
                "Deck source saved but SPA preview was not built. "
                "Check SANDBOX_PROVIDER and E2B_API_KEY, or inspect build logs."
            )
            if not spec.preview_url
            else None,
        )
    )
    if payload.get("warning"):
        payload["status"] = payload.get("status") or "queued"
    return payload


@tool(
    name="render_html_ppt",
    description=(
        "Publish a html-ppt deck from a complete index.html document and show it in chat. "
        "Use after load_skill html-ppt. Asset links like ../../assets/ are rewritten to ./assets/. "
        "On error, fix the HTML and call again."
    ),
)
def render_html_ppt_tool(
    source: Annotated[str, "Complete html-ppt index.html document (<html>...</html>)."],
    title: Annotated[str, "Short deck title for the artifact card."] = "HTML deck",
) -> dict[str, Any]:
    ctx = get_run_artifact_state()
    if ctx is None:
        return {"status": "error", "message": "Artifact context unavailable for this run."}

    normalized = (source or "").strip()
    if not normalized:
        return {
            "status": "error",
            "message": "HTML source is empty.",
            "hint": "Provide a full html-ppt deck as index.html with <section class=\"slide\"> blocks.",
        }

    ctx.last_source = normalized

    try:
        dist_files = build_html_ppt_dist(normalized)
    except (ValueError, FileNotFoundError) as exc:
        return {
            "status": "error",
            "message": str(exc).strip() or "Failed to prepare html-ppt preview.",
            "hint": "Ensure the document is valid html-ppt markup and assets are referenced via ../../assets/.",
        }

    try:
        spec = build_html_ppt_artifact_spec(
            title=title,
            source=dist_files["index.html"].decode("utf-8"),
            chat_id=ctx.chat_id,
            dist_files=dist_files,
        )
    except OSError as exc:
        return {
            "status": "error",
            "message": str(exc).strip() or "Failed to persist html-ppt artifact.",
            "hint": "Check ARTIFACT_STORAGE and BLOB_READ_WRITE_TOKEN.",
        }
    except RuntimeError as exc:
        return {
            "status": "error",
            "message": str(exc).strip() or "Failed to persist html-ppt artifact.",
            "hint": "Check ARTIFACT_STORAGE and BLOB_READ_WRITE_TOKEN.",
        }

    payload = _queue_artifact(spec)
    payload.update(slide_tool_payload(spec))
    return payload

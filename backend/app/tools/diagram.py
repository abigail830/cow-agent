"""Diagram rendering tools — PlantUML and future diagram backends."""

from __future__ import annotations

import re
from typing import Annotated, Any

from agent_framework import tool

from app.diagram.context import get_run_diagram_state
from app.diagram.plantuml_renderer import PlantUmlRenderError, render_plantuml
from app.proposal.artifact_spec import ArtifactSpec
from app.proposal.storage import new_artifact_id, save_diagram_artifact

_PREVIEW_CHAR_LIMIT = 120_000
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _artifact_download_url(chat_id, artifact_id: str, *, variant: str | None = None) -> str:
    base = f"/api/v1/chats/{chat_id}/artifacts/{artifact_id}"
    if variant:
        return f"{base}?format={variant}"
    return base


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug[:48] or "diagram"


def _build_diagram_artifact(
    *,
    title: str,
    svg: str,
    png: bytes,
    source: str,
    chat_id,
) -> ArtifactSpec:
    artifact_id = new_artifact_id(prefix="diag")
    filename_base = _slugify(title)
    svg_filename = f"{filename_base}.svg"
    png_filename = f"{filename_base}.png"
    download_url = None
    png_download_url = None
    if chat_id is not None:
        save_diagram_artifact(
            chat_id,
            artifact_id,
            svg=svg,
            png=png,
            filename_base=filename_base,
        )
        download_url = _artifact_download_url(chat_id, artifact_id)
        png_download_url = _artifact_download_url(chat_id, artifact_id, variant="png")
    preview_truncated = len(svg) > _PREVIEW_CHAR_LIMIT
    preview_svg = "" if preview_truncated else svg
    return ArtifactSpec(
        kind="diagram_svg",
        title=title,
        format="svg",
        content=preview_svg,
        filename=svg_filename,
        artifact_id=artifact_id,
        download_url=download_url,
        png_download_url=png_download_url,
        png_filename=png_filename,
        preview_truncated=preview_truncated,
        source=source,
    )


def _queue_artifact(spec: ArtifactSpec) -> dict[str, Any]:
    ctx = get_run_diagram_state()
    if ctx is None:
        return {"status": "error", "message": "Diagram context unavailable for this run."}
    queued = ctx.queue_artifact(spec)
    payload = spec.model_dump(mode="json")
    payload["status"] = "queued" if queued else "deduplicated"
    payload["queued"] = queued
    return payload


@tool(
    name="render_plantuml",
    description=(
        "Render PlantUML source to an SVG diagram artifact shown in chat. "
        "Always call this after drafting or editing PlantUML — do not ask the user "
        "to render elsewhere. On error, read the message, fix the script, and retry "
        "until render succeeds or you need user input."
    ),
)
def render_plantuml_tool(
    source: Annotated[str, "Complete PlantUML source (@startuml ... @enduml)."],
    title: Annotated[str, "Short diagram title for the artifact card."] = "PlantUML diagram",
) -> dict[str, Any]:
    ctx = get_run_diagram_state()
    if ctx is None:
        return {"status": "error", "message": "Diagram context unavailable for this run."}

    result = render_plantuml(source)
    if isinstance(result, PlantUmlRenderError):
        ctx.last_source = result.normalized_source
        return {
            "status": "error",
            "message": result.message,
            "renderer": result.renderer,
            "normalized_source": result.normalized_source,
            "hint": "Fix the PlantUML syntax or includes, then call render_plantuml again.",
        }

    ctx.last_source = result.normalized_source
    try:
        spec = _build_diagram_artifact(
            title=title.strip() or "PlantUML diagram",
            svg=result.svg,
            png=result.png,
            source=result.normalized_source,
            chat_id=ctx.chat_id,
        )
    except OSError as exc:
        return {
            "status": "error",
            "message": str(exc).strip() or "Failed to persist diagram artifact.",
            "renderer": "storage",
            "normalized_source": result.normalized_source,
            "hint": "Artifact storage is unavailable. Check ARTIFACT_STORAGE and BLOB_READ_WRITE_TOKEN.",
        }
    except RuntimeError as exc:
        return {
            "status": "error",
            "message": str(exc).strip() or "Failed to persist diagram artifact.",
            "renderer": "storage",
            "normalized_source": result.normalized_source,
            "hint": "Artifact storage is unavailable. Check ARTIFACT_STORAGE and BLOB_READ_WRITE_TOKEN.",
        }
    payload = _queue_artifact(spec)
    payload["download_url"] = spec.download_url
    payload["png_download_url"] = spec.png_download_url
    payload["filename"] = spec.filename
    payload["png_filename"] = spec.png_filename
    payload["format"] = "svg"
    return payload

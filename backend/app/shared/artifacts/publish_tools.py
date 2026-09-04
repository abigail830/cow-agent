"""Publish sandbox deliverables as chat artifacts."""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool

from app.shared.artifacts.content_studio_builder import build_content_studio_artifact_spec
from app.shared.artifacts.context import get_run_artifact_state
from app.shared.sandbox.providers.content_studio import ContentStudioSandboxError, get_content_studio_sandbox

PUBLISH_TOOL_NAMES = frozenset({"publish_artifact"})


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
    name="publish_artifact",
    description=(
        "Publish a final deliverable from the sandbox to the chat UI as a downloadable artifact. "
        "Call after the file is fully written (docx, pptx, html). "
        "Do not publish intermediate scratch files unless the user asked."
    ),
)
def publish_artifact_tool(
    path: Annotated[str, "Absolute sandbox path to the final file, e.g. /home/user/content-studio/report.docx."],
    title: Annotated[str, "Short title for the download card."] = "",
) -> dict[str, Any]:
    ctx = get_run_artifact_state()
    if ctx is None:
        return {"status": "error", "message": "Artifact context unavailable for this run."}

    try:
        file_bytes = get_content_studio_sandbox().read_bytes(path)
    except ContentStudioSandboxError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": str(exc).strip() or "Failed to read deliverable from sandbox."}

    if not file_bytes:
        return {"status": "error", "message": "Deliverable file is empty."}

    try:
        spec = build_content_studio_artifact_spec(
            sandbox_path=path,
            file_bytes=file_bytes,
            title=title,
            chat_id=ctx.chat_id,
        )
    except OSError as exc:
        return {"status": "error", "message": str(exc).strip() or "Failed to persist artifact."}
    except RuntimeError as exc:
        return {"status": "error", "message": str(exc).strip() or "Failed to persist artifact."}

    payload = _queue_artifact(spec)
    payload["filename"] = spec.filename
    payload["format"] = spec.format
    payload["download_url"] = spec.download_url
    payload["preview_url"] = spec.preview_url
    return payload


PUBLISH_BUILTIN_TOOLS = {
    "publish_artifact": publish_artifact_tool,
}

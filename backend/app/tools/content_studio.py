"""Content Studio sandbox and artifact publishing tools."""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool

from app.artifacts.content_studio_builder import build_content_studio_artifact_spec
from app.artifacts.context import get_run_artifact_state
from app.sandbox.providers.content_studio import ContentStudioSandboxError, get_content_studio_sandbox

_LOG_TAIL_CHARS = 8000
_READ_TAIL_CHARS = 12000


def _queue_artifact(spec) -> dict[str, Any]:
    ctx = get_run_artifact_state()
    if ctx is None:
        return {"status": "error", "message": "Artifact context unavailable for this run."}
    queued = ctx.queue_artifact(spec)
    payload = spec.model_dump(mode="json")
    payload["status"] = "queued" if queued else "deduplicated"
    payload["queued"] = queued
    return payload


def _command_payload(result: dict[str, str | int | bool]) -> dict[str, Any]:
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    exit_code = int(result.get("exit_code") or 0)
    payload: dict[str, Any] = {
        "status": "ok" if exit_code == 0 else "error",
        "exit_code": exit_code,
        "cwd": result.get("cwd"),
        "stdout": stdout[-_LOG_TAIL_CHARS:],
        "stderr": stderr[-_LOG_TAIL_CHARS:],
    }
    if exit_code != 0:
        detail = (stderr or stdout).strip()
        payload["message"] = detail[:2000] if detail else f"Command failed with exit code {exit_code}."
    return payload


@tool(
    name="sandbox_run_command",
    description=(
        "Run a shell command in the Content Studio E2B sandbox. "
        "Use for Node scripts (docx/pptx), pandoc, python helpers, etc. "
        "Default cwd is /home/user/content-studio. On non-zero exit, read stderr and retry with fixes."
    ),
)
def sandbox_run_command_tool(
    command: Annotated[str, "Shell command to execute."],
    cwd: Annotated[str, "Working directory inside the sandbox."] = "/home/user/content-studio",
) -> dict[str, Any]:
    try:
        result = get_content_studio_sandbox().run_command(command, cwd=cwd)
    except ContentStudioSandboxError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": str(exc).strip() or "Sandbox command failed."}
    return _command_payload(result)


@tool(
    name="sandbox_read_file",
    description=(
        "Read a UTF-8 text file from the Content Studio sandbox workspace "
        "(paths under /home/user/content-studio). Use for skill references, scripts, and generated source."
    ),
)
def sandbox_read_file_tool(
    path: Annotated[str, "Absolute or workspace-relative sandbox path."],
) -> dict[str, Any]:
    try:
        result = get_content_studio_sandbox().read_file(path)
    except ContentStudioSandboxError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": str(exc).strip() or "Sandbox read failed."}

    content = str(result.get("content") or "")
    truncated = bool(result.get("truncated"))
    if len(content) > _READ_TAIL_CHARS:
        content = content[:_READ_TAIL_CHARS]
        truncated = True
    return {
        "status": "ok",
        "path": result.get("path"),
        "content": content,
        "truncated": truncated,
        "bytes": result.get("bytes"),
    }


@tool(
    name="sandbox_write_file",
    description=(
        "Write a UTF-8 text file in the Content Studio sandbox "
        "(e.g. build-deck.js, HTML source). Parent directories are created as needed."
    ),
)
def sandbox_write_file_tool(
    path: Annotated[str, "Absolute or workspace-relative sandbox path."],
    content: Annotated[str, "Full file contents to write."],
) -> dict[str, Any]:
    try:
        result = get_content_studio_sandbox().write_file(path, content)
    except ContentStudioSandboxError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": str(exc).strip() or "Sandbox write failed."}
    return {
        "status": "ok",
        "path": result.get("path"),
        "bytes": result.get("bytes"),
    }


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

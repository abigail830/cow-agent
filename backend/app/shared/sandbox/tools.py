"""E2B sandbox file and command tools — shared capability for content-studio and similar agents."""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool

from app.shared.sandbox.providers.content_studio import ContentStudioSandboxError, get_content_studio_sandbox

SANDBOX_TOOL_NAMES = frozenset(
    {
        "sandbox_run_command",
        "sandbox_read_file",
        "sandbox_write_file",
    }
)

_LOG_TAIL_CHARS = 8000
_READ_TAIL_CHARS = 12000
_DEFAULT_CWD = "/home/user/content-studio"


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
        payload["message"] = detail[:2000] if detail else f"Command failed with exit_code {exit_code}."
    return payload


@tool(
    name="sandbox_run_command",
    description=(
        "Run a shell command in the E2B sandbox workspace. "
        "Use for Node scripts (docx/pptx), pandoc, python helpers, etc. "
        f"Default cwd is {_DEFAULT_CWD}. On non-zero exit, read stderr and retry with fixes."
    ),
)
def sandbox_run_command_tool(
    command: Annotated[str, "Shell command to execute."],
    cwd: Annotated[str, "Working directory inside the sandbox."] = _DEFAULT_CWD,
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
        "Read a UTF-8 text file from the E2B sandbox workspace "
        f"(paths under {_DEFAULT_CWD}). Use for skill references, scripts, and generated source."
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
        "Write a UTF-8 text file in the E2B sandbox "
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


SANDBOX_BUILTIN_TOOLS = {
    "sandbox_run_command": sandbox_run_command_tool,
    "sandbox_read_file": sandbox_read_file_tool,
    "sandbox_write_file": sandbox_write_file_tool,
}

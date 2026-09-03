"""Content Studio agent sandbox — E2B command/file execution."""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

from app.sandbox.e2b_session import acquire_e2b_sandbox, get_e2b_session_key, release_e2b_session

logger = logging.getLogger(__name__)

WORK_DIR = "/home/user/content-studio"
_ALLOWED_ROOTS = (WORK_DIR, f"{WORK_DIR}/skills")


class ContentStudioSandboxError(Exception):
    pass


class ContentStudioSandbox:
    name = "content_studio_e2b"

    def __init__(
        self,
        *,
        api_key: str | None,
        template: str | None,
        timeout_seconds: float = 180.0,
        reuse_session: bool = True,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._template = (template or "").strip() or None
        self._timeout_seconds = max(30.0, timeout_seconds)
        self._reuse_session = reuse_session

    def _create_sandbox(self) -> object:
        try:
            from e2b_code_interpreter import Sandbox
        except ImportError as exc:
            raise ContentStudioSandboxError(
                "e2b-code-interpreter is not installed. Run: pip install e2b-code-interpreter"
            ) from exc

        if not self._api_key:
            raise ContentStudioSandboxError("E2B_API_KEY is not configured.")

        timeout = int(self._timeout_seconds)
        if self._template:
            return Sandbox.create(template=self._template, api_key=self._api_key, timeout=timeout)
        return Sandbox.create(api_key=self._api_key, timeout=timeout)

    def _acquire(self) -> tuple[object, bool]:
        session_key = get_e2b_session_key() if self._reuse_session else None
        if session_key:
            return acquire_e2b_sandbox(
                session_key=session_key,
                workdir=WORK_DIR,
                create_fn=self._create_sandbox,
            )
        return self._create_sandbox(), True

    @staticmethod
    def resolve_path(path: str) -> str:
        raw = (path or "").strip()
        if not raw:
            raise ContentStudioSandboxError("Path is required.")
        resolved = PurePosixPath(raw if raw.startswith("/") else f"{WORK_DIR}/{raw.lstrip('/')}")
        normalized = str(resolved)
        if ".." in normalized.split("/"):
            raise ContentStudioSandboxError(f"Path escapes sandbox workspace: {path}")
        if not any(normalized == root or normalized.startswith(f"{root}/") for root in _ALLOWED_ROOTS):
            raise ContentStudioSandboxError(
                f"Path must be under {WORK_DIR} (got {normalized})."
            )
        return normalized

    def run_command(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, str | int]:
        cmd = (command or "").strip()
        if not cmd:
            raise ContentStudioSandboxError("Command is required.")

        workdir = self.resolve_path(cwd or WORK_DIR)
        timeout = timeout_seconds if timeout_seconds is not None else self._timeout_seconds
        sandbox, created = self._acquire()
        result = sandbox.commands.run(  # type: ignore[attr-defined]
            cmd,
            cwd=workdir,
            timeout=timeout,
        )
        stdout = getattr(result, "stdout", "") or ""
        stderr = getattr(result, "stderr", "") or ""
        exit_code = int(getattr(result, "exit_code", 1) or 0)
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "cwd": workdir,
            "sandbox_created": created,
        }

    def read_file(self, path: str, *, max_bytes: int = 500_000) -> dict[str, str | int | bool]:
        resolved = self.resolve_path(path)
        sandbox, created = self._acquire()
        raw = sandbox.files.read(resolved)  # type: ignore[attr-defined]
        if isinstance(raw, str):
            data = raw.encode("utf-8")
            text = raw
            truncated = False
        else:
            data = bytes(raw)
            truncated = len(data) > max_bytes
            if truncated:
                data = data[:max_bytes]
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                raise ContentStudioSandboxError(
                    f"File is binary or not UTF-8 ({resolved}). Use publish_artifact for deliverables."
                ) from None
        return {
            "path": resolved,
            "content": text,
            "bytes": len(data),
            "truncated": truncated,
            "sandbox_created": created,
        }

    def write_file(self, path: str, content: str) -> dict[str, str | int | bool]:
        resolved = self.resolve_path(path)
        sandbox, created = self._acquire()
        sandbox.files.write(resolved, content)  # type: ignore[attr-defined]
        return {
            "path": resolved,
            "bytes": len(content.encode("utf-8")),
            "sandbox_created": created,
        }

    def read_bytes(self, path: str, *, max_bytes: int = 20_000_000) -> bytes:
        resolved = self.resolve_path(path)
        sandbox, _created = self._acquire()
        raw = sandbox.files.read(resolved)  # type: ignore[attr-defined]
        if isinstance(raw, str):
            data = raw.encode("utf-8")
        else:
            data = bytes(raw)
        if len(data) > max_bytes:
            raise ContentStudioSandboxError(
                f"File exceeds publish limit ({len(data)} bytes > {max_bytes})."
            )
        return data

    @staticmethod
    def release_run_session() -> None:
        release_e2b_session()


def get_content_studio_sandbox() -> ContentStudioSandbox:
    from app.config import get_settings

    settings = get_settings()
    return ContentStudioSandbox(
        api_key=settings.e2b_api_key,
        template=settings.e2b_content_studio_template,
        timeout_seconds=settings.sandbox_timeout_seconds,
        reuse_session=settings.sandbox_reuse_session,
    )

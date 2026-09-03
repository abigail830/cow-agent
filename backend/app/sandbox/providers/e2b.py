"""Build Slidev decks inside an E2B sandbox."""

from __future__ import annotations

import logging

from app.sandbox.e2b_session import acquire_e2b_sandbox, get_e2b_session_key, release_e2b_session
from app.sandbox.templates import SLIDEV_PACKAGE_JSON
from app.sandbox.types import SlidevBuildOutput

logger = logging.getLogger(__name__)

_DEFAULT_WORKDIR = "/home/user"
_TEMPLATE_WORKDIR = "/opt/slidev"


class E2BSandboxProvider:
    name = "e2b"

    def __init__(
        self,
        *,
        api_key: str | None,
        timeout_seconds: float = 180.0,
        export_pdf: bool = False,
        template: str | None = None,
        reuse_session: bool = True,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._timeout_seconds = max(30.0, timeout_seconds)
        self._export_pdf = export_pdf
        self._template = (template or "").strip() or None
        self._reuse_session = reuse_session

    def _workdir(self) -> str:
        return _TEMPLATE_WORKDIR if self._template else _DEFAULT_WORKDIR

    def _slides_path(self, workdir: str) -> str:
        return f"{workdir}/slides.md"

    def _package_path(self, workdir: str) -> str:
        return f"{workdir}/package.json"

    def _dist_dir(self, workdir: str) -> str:
        return f"{workdir}/dist"

    def build_slidev(
        self,
        *,
        slides_md: str,
        exports: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> SlidevBuildOutput:
        _ = exports
        if not self._api_key:
            return SlidevBuildOutput(error="E2B_API_KEY is not configured.")

        timeout = timeout_seconds if timeout_seconds is not None else self._timeout_seconds
        workdir = self._workdir()
        slides_path = self._slides_path(workdir)
        dist_dir = self._dist_dir(workdir)
        logs: list[str] = []

        try:
            from e2b_code_interpreter import Sandbox
        except ImportError:
            return SlidevBuildOutput(
                error="e2b-code-interpreter is not installed. Run: pip install e2b-code-interpreter",
            )

        session_key = get_e2b_session_key() if self._reuse_session else None
        sandbox = None
        owns_sandbox = False

        try:
            def _create_sandbox() -> object:
                if self._template:
                    return Sandbox.create(
                        template=self._template,
                        api_key=self._api_key,
                        timeout=int(timeout),
                    )
                return Sandbox.create(api_key=self._api_key, timeout=int(timeout))

            if session_key:
                sandbox, created = acquire_e2b_sandbox(
                    session_key=session_key,
                    workdir=workdir,
                    create_fn=_create_sandbox,
                )
                owns_sandbox = False
                if created:
                    logs.append(f"E2B sandbox created (session={session_key}, template={self._template or 'default'}).")
                else:
                    logs.append(f"E2B sandbox reused (session={session_key}).")
            else:
                sandbox = _create_sandbox()
                owns_sandbox = True
                logs.append(f"E2B sandbox created (ephemeral, template={self._template or 'default'}).")

            sandbox.files.write(slides_path, slides_md)
            if not self._template:
                sandbox.files.write(self._package_path(workdir), SLIDEV_PACKAGE_JSON)
                install = sandbox.commands.run(
                    "npm install --no-audit --no-fund 2>&1",
                    cwd=workdir,
                    timeout=timeout,
                )
                logs.append(_format_command_result("npm install", install))
                if getattr(install, "exit_code", 1) != 0:
                    return SlidevBuildOutput(
                        logs="\n\n".join(logs),
                        error=_command_error("npm install", install),
                    )
            else:
                logs.append("Skipped npm install (E2B_SLIDEV_TEMPLATE preinstall).")

            build = sandbox.commands.run(
                "npx slidev build slides.md --out dist --base ./ 2>&1",
                cwd=workdir,
                timeout=timeout,
            )
            logs.append(_format_command_result("slidev build", build))
            if getattr(build, "exit_code", 1) != 0:
                return SlidevBuildOutput(
                    logs="\n\n".join(logs),
                    error=_command_error("slidev build", build),
                )

            pdf_bytes: bytes | None = None
            if self._export_pdf:
                export = sandbox.commands.run(
                    "npx slidev export slides.md --format pdf --output deck.pdf 2>&1",
                    cwd=workdir,
                    timeout=timeout,
                )
                logs.append(_format_command_result("slidev export", export))
                if getattr(export, "exit_code", 1) == 0:
                    try:
                        pdf_bytes = sandbox.files.read(f"{workdir}/deck.pdf")
                        if isinstance(pdf_bytes, str):
                            pdf_bytes = pdf_bytes.encode("utf-8")
                    except Exception as exc:
                        logs.append(f"PDF read failed: {exc}")

            dist_files = _collect_dist_files(sandbox, dist_dir, workdir, logs)
            if not dist_files:
                return SlidevBuildOutput(
                    logs="\n\n".join(logs),
                    error="Slidev build produced no dist files.",
                )

            return SlidevBuildOutput(
                dist_files=dist_files,
                pdf_bytes=pdf_bytes,
                logs="\n\n".join(logs),
            )
        except Exception as exc:
            logger.exception("E2B Slidev build failed")
            logs.append(f"Exception: {exc}")
            return SlidevBuildOutput(logs="\n\n".join(logs), error=str(exc).strip() or "E2B build failed")
        finally:
            if owns_sandbox and sandbox is not None:
                try:
                    sandbox.kill()
                except Exception:
                    logger.debug("E2B sandbox kill failed", exc_info=True)

    @staticmethod
    def release_run_session() -> None:
        release_e2b_session()


def _format_command_result(label: str, result: object) -> str:
    stdout = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    exit_code = getattr(result, "exit_code", "?")
    parts = [f"=== {label} (exit {exit_code}) ==="]
    if stdout.strip():
        parts.append(stdout.strip())
    if stderr.strip():
        parts.append(stderr.strip())
    return "\n".join(parts)


def _command_error(label: str, result: object) -> str:
    stdout = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    detail = (stderr or stdout or "").strip()
    exit_code = getattr(result, "exit_code", "?")
    if detail:
        return f"{label} failed (exit {exit_code}): {detail[:2000]}"
    return f"{label} failed (exit {exit_code})"


def _collect_dist_files(
    sandbox: object,
    dist_dir: str,
    workdir: str,
    logs: list[str],
) -> dict[str, bytes]:
    list_result = sandbox.commands.run(  # type: ignore[attr-defined]
        f"find {dist_dir} -type f 2>/dev/null || true",
        cwd=workdir,
        timeout=60,
    )
    stdout = getattr(list_result, "stdout", "") or ""
    paths = [line.strip() for line in stdout.splitlines() if line.strip()]
    dist_files: dict[str, bytes] = {}

    for abs_path in paths:
        if not abs_path.startswith(dist_dir):
            continue
        rel = abs_path[len(dist_dir) :].lstrip("/")
        if not rel:
            continue
        try:
            raw = sandbox.files.read(abs_path)  # type: ignore[attr-defined]
            if isinstance(raw, str):
                raw = raw.encode("utf-8")
            dist_files[rel] = raw
        except Exception as exc:
            logs.append(f"Failed to read {abs_path}: {exc}")

    if not dist_files:
        logs.append("find dist returned no readable files")
    return dist_files

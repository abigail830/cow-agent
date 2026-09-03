"""Render PlantUML source via a pinned backend renderer."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from app.config import get_settings

RenderFormat = Literal["svg", "png"]

_START_RE = re.compile(r"@start(uml|dot|salt|ditaa|gantt|mindmap|wbs|yaml|json|flow|board|chronology)\b", re.I)
_END_RE = re.compile(r"@end(uml|dot|salt|ditaa|gantt|mindmap|wbs|yaml|json|flow|board|chronology)\b", re.I)


@dataclass(frozen=True)
class PlantUmlRenderResult:
    svg: str
    png: bytes
    normalized_source: str


@dataclass(frozen=True)
class PlantUmlRenderError:
    message: str
    normalized_source: str
    renderer: str


def normalize_plantuml_source(source: str) -> str:
    text = (source or "").strip()
    if not text:
        raise ValueError("PlantUML source is empty.")

    if not _START_RE.search(text):
        text = f"@startuml\n{text}"
    if not _END_RE.search(text):
        text = f"{text}\n@enduml"
    return text.strip() + "\n"


def _render_via_kroki(source: str, *, base_url: str, timeout: float, output: RenderFormat) -> str | bytes:
    url = f"{base_url.rstrip('/')}/plantuml/{output}"
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, content=source.encode("utf-8"), headers={"Content-Type": "text/plain"})
    if response.status_code != 200:
        detail = (response.text or "").strip() or response.reason_phrase or "Unknown Kroki error"
        raise ValueError(detail)
    if output == "svg":
        body = response.text
        if not body.lstrip().startswith("<"):
            raise ValueError(body.strip() or "Renderer returned non-SVG payload.")
        return body
    payload = response.content
    if not payload.startswith(b"\x89PNG"):
        detail = (response.text or "").strip()
        raise ValueError(detail or "Renderer returned non-PNG payload.")
    return payload


def _render_via_local_jar(
    source: str,
    *,
    jar_path: Path,
    timeout: float,
    output: RenderFormat,
) -> str | bytes:
    if not jar_path.is_file():
        raise ValueError(f"PlantUML jar not found: {jar_path}")
    java = shutil.which("java")
    if not java:
        raise ValueError("Java runtime not found; install Java or set PLANTUML_RENDERER=kroki.")

    flag = "-tsvg" if output == "svg" else "-tpng"
    ext = ".svg" if output == "svg" else ".png"

    with tempfile.TemporaryDirectory(prefix="plantuml-") as tmp:
        tmp_dir = Path(tmp)
        puml_path = tmp_dir / "diagram.puml"
        puml_path.write_text(source, encoding="utf-8")
        proc = subprocess.run(
            [java, "-jar", str(jar_path), flag, str(puml_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out_path = tmp_dir / f"diagram{ext}"
        if proc.returncode != 0 or not out_path.is_file():
            stderr = (proc.stderr or proc.stdout or "").strip()
            raise ValueError(stderr or f"PlantUML local {output} render failed.")
        if output == "svg":
            return out_path.read_text(encoding="utf-8")
        return out_path.read_bytes()


def _render_output(
    source: str,
    *,
    renderer: str,
    timeout: float,
    output: RenderFormat,
) -> str | bytes:
    if renderer == "local":
        return _render_via_local_jar(
            source,
            jar_path=Path(get_settings().plantuml_jar_path),
            timeout=timeout,
            output=output,
        )
    return _render_via_kroki(
        source,
        base_url=get_settings().kroki_url,
        timeout=timeout,
        output=output,
    )


def render_plantuml(source: str) -> PlantUmlRenderResult | PlantUmlRenderError:
    settings = get_settings()
    normalized = normalize_plantuml_source(source)
    renderer = settings.plantuml_renderer.strip().lower() or "kroki"
    timeout = settings.plantuml_render_timeout_seconds

    try:
        svg = _render_output(normalized, renderer=renderer, timeout=timeout, output="svg")
        png = _render_output(normalized, renderer=renderer, timeout=timeout, output="png")
    except Exception as exc:
        return PlantUmlRenderError(
            message=str(exc).strip() or type(exc).__name__,
            normalized_source=normalized,
            renderer=renderer,
        )

    assert isinstance(svg, str)
    assert isinstance(png, bytes)
    return PlantUmlRenderResult(svg=svg, png=png, normalized_source=normalized)

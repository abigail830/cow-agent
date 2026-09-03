"""Tests for E2B session reuse, build cache, and async slide jobs."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.artifacts.context import init_run_artifact_state, reset_run_artifact_state
from app.artifacts.spec import ArtifactSpec
from app.sandbox.e2b_session import acquire_e2b_sandbox, release_e2b_session
from app.sandbox.providers.e2b import E2BSandboxProvider
from app.sandbox.types import SlidevBuildOutput
from app.slide.build_cache import get_cached_build, put_cached_build, slide_build_cache_key
from app.slide.build_jobs import (
    drain_completed_slide_build_jobs,
    has_pending_slide_build_jobs,
    reset_slide_build_jobs,
    submit_slide_build_job,
)
from app.slide.renderer import SlideRenderer


def test_e2b_session_reuse() -> None:
    created = {"count": 0}

    class FakeSandbox:
        def kill(self) -> None:
            return None

    def _create() -> FakeSandbox:
        created["count"] += 1
        return FakeSandbox()

    release_e2b_session("chat-1")
    sandbox_a, new_a = acquire_e2b_sandbox(session_key="chat-1", workdir="/opt/slidev", create_fn=_create)
    sandbox_b, new_b = acquire_e2b_sandbox(session_key="chat-1", workdir="/opt/slidev", create_fn=_create)
    assert created["count"] == 1
    assert sandbox_a is sandbox_b
    assert new_a is True
    assert new_b is False
    release_e2b_session("chat-1")


def test_e2b_template_skips_npm_install(monkeypatch) -> None:
    provider = E2BSandboxProvider(api_key="test-key", template="slidev-builder-v1", reuse_session=False)
    commands: list[str] = []

    class FakeSandbox:
        files = SimpleNamespace(write=lambda *_a, **_k: None)

        @property
        def commands(self) -> SimpleNamespace:
            return SimpleNamespace(run=self._run)

        def _run(self, cmd: str, **_kwargs: object) -> SimpleNamespace:
            commands.append(cmd)
            if "slidev build" in cmd:
                return SimpleNamespace(stdout="built", stderr="", exit_code=0)
            return SimpleNamespace(stdout="", stderr="", exit_code=0)

        def kill(self) -> None:
            return None

    def _create(**kwargs: object) -> FakeSandbox:
        commands.append(f"template={kwargs.get('template')}")
        return FakeSandbox()

    monkeypatch.setattr("e2b_code_interpreter.Sandbox", SimpleNamespace(create=_create))

    def _fake_collect(sandbox: object, dist_dir: str, workdir: str, logs: list[str]) -> dict[str, bytes]:
        _ = sandbox, dist_dir, workdir, logs
        return {"index.html": b"<html></html>"}

    monkeypatch.setattr("app.sandbox.providers.e2b._collect_dist_files", _fake_collect)

    result = provider.build_slidev(slides_md="---\ntitle: X\n---\n\n# Hi")
    assert result.ok
    assert any("template=slidev-builder-v1" in cmd for cmd in commands)
    assert not any("npm install" in cmd for cmd in commands)
    assert any("slidev build" in cmd for cmd in commands)


def test_slide_build_cache_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORAGE", "local")
    monkeypatch.setenv("SANDBOX_SLIDEV_CACHE", "true")
    from app.config import get_settings

    get_settings.cache_clear()

    key = slide_build_cache_key(
        "# Deck",
        export_pdf=False,
        provider="e2b",
        template="slidev-builder-v1",
    )
    output = SlidevBuildOutput(dist_files={"index.html": b"<html></html>"})
    put_cached_build(key, output)
    cached = get_cached_build(key)
    assert cached is not None
    assert cached.dist_files["index.html"] == b"<html></html>"
    assert "cache hit" in (cached.logs or "")

    get_settings.cache_clear()


def test_slide_renderer_uses_cache(monkeypatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORAGE", "local")
    monkeypatch.setenv("SANDBOX_PROVIDER", "local")
    monkeypatch.setenv("SANDBOX_SLIDEV_CACHE", "true")
    from app.config import get_settings

    get_settings.cache_clear()

    calls = {"count": 0}
    from app.sandbox.providers import local as local_provider

    def _counting_build(self, **kwargs: object) -> SlidevBuildOutput:
        _ = self, kwargs
        calls["count"] += 1
        return SlidevBuildOutput(dist_files={"index.html": b"<html></html>"})

    monkeypatch.setattr(local_provider.LocalSandboxProvider, "build_slidev", _counting_build)

    source = f"---\ntitle: A\n---\n\n# One {uuid.uuid4().hex}"
    first = SlideRenderer().build(source)
    second = SlideRenderer().build(source)
    assert first.ok
    assert second.ok
    assert calls["count"] == 1

    get_settings.cache_clear()


def test_async_slide_build_job(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    reset_slide_build_jobs(chat_id)

    def _fake_build(slides_md: str) -> SlidevBuildOutput:
        _ = slides_md
        return SlidevBuildOutput(dist_files={"index.html": b"<html></html>"})

    def _fake_spec(**kwargs: object) -> ArtifactSpec:
        return ArtifactSpec(
            kind="slide_deck",
            title=str(kwargs.get("title") or "Demo"),
            format="slidev",
            content=str(kwargs.get("source") or ""),
            filename="demo.md",
            artifact_id="slide-test123",
        )

    monkeypatch.setattr("app.slide.build_jobs.run_slidev_build", _fake_build)
    monkeypatch.setattr("app.slide.build_jobs.build_slide_artifact_spec", _fake_spec)

    job_id = submit_slide_build_job(chat_id=chat_id, slides_md="# Deck", title="Demo")
    assert job_id.startswith("slide-job-")

    import time

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and has_pending_slide_build_jobs(chat_id):
        time.sleep(0.05)

    specs = drain_completed_slide_build_jobs(chat_id)
    assert len(specs) == 1
    assert specs[0].artifact_id == "slide-test123"
    reset_slide_build_jobs(chat_id)


def test_reset_run_artifact_state_releases_e2b_session() -> None:
    reset_run_artifact_state()
    chat_id = uuid.uuid4()
    init_run_artifact_state(chat_id=chat_id)
    reset_run_artifact_state()

"""Tests for Slidev build executor and E2B provider guards."""

from __future__ import annotations

from types import SimpleNamespace

from app.sandbox.providers.e2b import E2BSandboxProvider
from app.sandbox.types import SlidevBuildOutput
from app.slide.build_executor import run_slidev_build


def test_e2b_provider_fails_fast_on_npm_install_error(monkeypatch) -> None:
    provider = E2BSandboxProvider(api_key="test-key", timeout_seconds=60.0)

    class FakeSandbox:
        files = SimpleNamespace(write=lambda *_a, **_k: None)

        @property
        def commands(self) -> SimpleNamespace:
            return SimpleNamespace(run=self._run)

        def _run(self, cmd: str, **_kwargs: object) -> SimpleNamespace:
            if "npm install" in cmd:
                return SimpleNamespace(stdout="npm ERR!", stderr="", exit_code=1)
            raise AssertionError(f"unexpected command: {cmd}")

        def kill(self) -> None:
            return None

    monkeypatch.setattr(
        "e2b_code_interpreter.Sandbox",
        SimpleNamespace(create=lambda **_kwargs: FakeSandbox()),
    )

    result = provider.build_slidev(slides_md="---\ntitle: X\n---\n\n# Hi")
    assert result.error is not None
    assert "npm install" in result.error


def test_run_slidev_build_uses_worker_thread(monkeypatch) -> None:
    def fake_build(slides_md: str) -> SlidevBuildOutput:
        assert slides_md == "# Deck"
        return SlidevBuildOutput(dist_files={"index.html": b"<html></html>"})

    monkeypatch.setattr(
        "app.slide.build_executor.SlideRenderer",
        lambda: SimpleNamespace(build=fake_build),
    )

    result = run_slidev_build("# Deck")
    assert result.ok
    assert "index.html" in result.dist_files

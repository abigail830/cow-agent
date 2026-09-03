import pytest

from app.diagram.plantuml_renderer import normalize_plantuml_source, render_plantuml

_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


def test_normalize_plantuml_source_wraps_bare_body():
    out = normalize_plantuml_source("Alice -> Bob: hi")
    assert out.startswith("@startuml\n")
    assert "Alice -> Bob: hi" in out
    assert out.strip().endswith("@enduml")


def test_normalize_plantuml_source_preserves_markers():
    src = "@startuml\nA -> B\n@enduml"
    assert normalize_plantuml_source(src).strip() == src.strip()


def test_render_plantuml_success(monkeypatch):
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'

    class FakeResponse:
        def __init__(self, *, status_code: int, text: str = "", content: bytes = b""):
            self.status_code = status_code
            self.text = text
            self.content = content
            self.reason_phrase = "OK"

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, content, headers):
            assert b"@startuml" in content
            if url.endswith("/plantuml/svg"):
                return FakeResponse(status_code=200, text=svg)
            if url.endswith("/plantuml/png"):
                return FakeResponse(status_code=200, content=_PNG_HEADER)
            raise AssertionError(url)

    monkeypatch.setattr("app.diagram.plantuml_renderer.httpx.Client", FakeClient)
    result = render_plantuml("A -> B")
    assert result.svg == svg
    assert result.png.startswith(b"\x89PNG")
    assert "@startuml" in result.normalized_source


def test_render_plantuml_error(monkeypatch):
    class FakeResponse:
        status_code = 400
        text = "Syntax Error"
        reason_phrase = "Bad Request"

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, content, headers):
            return FakeResponse()

    monkeypatch.setattr("app.diagram.plantuml_renderer.httpx.Client", FakeClient)
    result = render_plantuml("bad syntax {{{")
    assert result.message == "Syntax Error"
    assert "@startuml" in result.normalized_source

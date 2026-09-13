"""Tests for Content Studio sandbox binary reads (publish_artifact path)."""

from __future__ import annotations

import pytest

from app.shared.sandbox.providers.content_studio import ContentStudioSandbox, ContentStudioSandboxError


class _FakeFiles:
    def __init__(self, *, text: str | None = None, data: bytes | None = None) -> None:
        self._text = text
        self._data = data
        self.last_format: str | None = None

    def read(self, path: str, format: str | None = None):  # noqa: A002
        self.last_format = format
        if format == "bytes":
            return bytearray(self._data or b"")
        return self._text if self._text is not None else bytes(self._data or b"")


class _FakeSandbox:
    def __init__(self, files: _FakeFiles) -> None:
        self.files = files


def test_read_sandbox_bytes_uses_bytes_format() -> None:
    payload = b"PK\x03\x04fake-docx"
    files = _FakeFiles(data=payload)
    result = ContentStudioSandbox._read_sandbox_bytes(_FakeSandbox(files), "/home/user/content-studio/a.docx")
    assert result == payload
    assert files.last_format == "bytes"


def test_read_sandbox_bytes_rejects_text_response() -> None:
    class _LegacyTextFiles:
        def read(self, path: str, format: str | None = None):  # noqa: A002
            if format == "bytes":
                raise TypeError("format not supported")
            return "PK\uFFFD corrupted"

    with pytest.raises(ContentStudioSandboxError, match="returned text for a binary"):
        ContentStudioSandbox._read_sandbox_bytes(_FakeSandbox(_LegacyTextFiles()), "/home/user/content-studio/a.docx")


def test_read_bytes_validates_ooxml_header(monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = ContentStudioSandbox(api_key="test-key", template=None, reuse_session=False)
    bad = b"not-a-zip"
    files = _FakeFiles(data=bad)

    def _acquire() -> tuple[object, bool]:
        return _FakeSandbox(files), True

    monkeypatch.setattr(sandbox, "_acquire", _acquire)
    with pytest.raises(ContentStudioSandboxError, match="looks corrupted"):
        sandbox.read_bytes("/home/user/content-studio/bad.docx")

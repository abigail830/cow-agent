import uuid

import pytest

from app.platform.docstore.figures import load_parsed_figure_resolved, normalize_figure_id


def test_normalize_figure_id_accepts_bare_and_dotted() -> None:
    assert normalize_figure_id("f1") == "f1"
    assert normalize_figure_id("f12.jpeg") == "f12"


def test_normalize_figure_id_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_figure_id("../f1")


def test_load_parsed_figure_resolved_probes_extensions(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()

    def fake_load(_chat_id, _attachment_id, figure_id, extension):
        if extension == "jpeg":
            raise FileNotFoundError("missing")
        if extension == "jpg":
            return b"png-bytes"
        raise FileNotFoundError("missing")

    monkeypatch.setattr("app.platform.docstore.figures.load_parsed_figure", fake_load)
    data, media_type = load_parsed_figure_resolved(chat_id, attachment_id, "f3")
    assert data == b"png-bytes"
    assert media_type == "image/jpeg"

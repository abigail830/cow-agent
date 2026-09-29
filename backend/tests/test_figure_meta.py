import uuid

import pytest

from app.platform.docstore.figure_meta import resolve_figure_storage_id, strip_figure_ref


def test_strip_figure_ref_strips_path_and_extension() -> None:
    assert strip_figure_ref("9ae33cb7502d788c42d6a014752613a7.jpeg") == "9ae33cb7502d788c42d6a014752613a7"
    assert strip_figure_ref("figures/f3.png") == "f3"


def test_resolve_figure_storage_id_maps_hash_to_meta_figure() -> None:
    meta = {
        "figures": [
            {
                "id": "f2",
                "line": 10,
                "sha256": "9ae33cb7502d788c42d6a014752613a7deadbeef",
                "filename": "f2.jpeg",
            }
        ]
    }
    assert resolve_figure_storage_id("9ae33cb7502d788c42d6a014752613a7", meta) == "f2"
    assert resolve_figure_storage_id("f2", meta) == "f2"


def test_resolve_figure_storage_id_rejects_unknown_token() -> None:
    with pytest.raises(ValueError):
        resolve_figure_storage_id("../etc/passwd", None)


def test_load_parsed_figure_resolved_uses_meta_hash_mapping(monkeypatch) -> None:
    from app.platform.docstore import figures as figures_mod

    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    calls: list[str] = []

    def fake_load(_chat_id, _attachment_id, figure_id, extension):
        calls.append(figure_id)
        if figure_id == "f1" and extension == "jpeg":
            return b"jpeg-bytes"
        raise FileNotFoundError("missing")

    monkeypatch.setattr(figures_mod, "load_parsed_figure", fake_load)
    monkeypatch.setattr(
        figures_mod,
        "_load_scoped_meta",
        lambda _scope: {
            "figures": [{"id": "f1", "sha256": "abcd1234abcd1234abcd1234abcd1234", "filename": "f1.jpeg"}]
        },
    )

    data, media_type = figures_mod.load_parsed_figure_resolved(
        chat_id,
        attachment_id,
        "abcd1234abcd1234abcd1234abcd1234.jpeg",
    )
    assert data == b"jpeg-bytes"
    assert media_type == "image/jpeg"
    assert calls == ["f1"]

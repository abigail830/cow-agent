import uuid

from app.shared.artifacts import storage as artifact_storage


def test_save_diagram_artifact_variants(tmp_path, monkeypatch):
    chat_id = uuid.uuid4()
    artifact_id = "diag-test123"
    monkeypatch.setattr(artifact_storage, "CHAT_ARTIFACTS_ROOT", tmp_path)
    monkeypatch.setattr(artifact_storage, "blob_storage_enabled", lambda: False)

    artifact_storage.save_diagram_artifact(
        chat_id,
        artifact_id,
        svg='<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        png=b"\x89PNG",
        filename_base="auth-flow",
    )

    svg_path = tmp_path / str(chat_id) / f"{artifact_id}.svg"
    png_path = tmp_path / str(chat_id) / f"{artifact_id}.png"
    assert svg_path.is_file()
    assert png_path.is_file()
    payload = artifact_storage.load_chat_artifact_payload(chat_id, artifact_id)
    assert payload is not None
    assert payload.filename == "auth-flow.svg"
    png_payload = artifact_storage.load_chat_artifact_payload(chat_id, artifact_id, variant="png")
    assert png_payload is not None
    assert png_payload.filename == "auth-flow.png"
    assert png_payload.media_type == "image/png"

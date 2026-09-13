import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.platform.attachments.run_state import AttachmentRecord, init_attachment_run_state, reset_attachment_run_state
from app.platform.attachments.services.ephemeral import resolve_vision_model_entry
from app.platform.attachments.services.vision import AttachmentVisionService
from app.platform.attachments.services.vision_resize import resize_image_for_vision
from app.platform.attachments.tools.pull_tools import analyze_image_tool

CHAT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ATTACHMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

def _tiny_png() -> bytes:
    import io

    from PIL import Image

    image = Image.new("RGB", (1, 1), color=(255, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


_TINY_PNG = _tiny_png()


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    yield
    reset_attachment_run_state()


@pytest.fixture
def _image_run_state() -> None:
    init_attachment_run_state(
        chat_id=CHAT_ID,
        attachments=[
            AttachmentRecord(
                attachment_id=ATTACHMENT_ID,
                chat_id=CHAT_ID,
                filename="chart.png",
                mime_type="image/png",
                provider="unify_lite",
                provider_file_id=f"inline:{ATTACHMENT_ID}",
                size_bytes=len(_TINY_PNG),
                gist="chart",
            )
        ],
    )


def test_resize_small_png_unchanged() -> None:
    result = resize_image_for_vision(_TINY_PNG, mime_type="image/png", max_edge=1568)
    assert result.resized is False
    assert result.data == _TINY_PNG


@pytest.mark.asyncio
async def test_vision_service_returns_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        DATABASE_URL="postgresql://x",
        REDIS_URL="redis://x",
        AZURE_API_KEY="k",
        AZURE_OPENAI_BASE_URL="https://example.openai.azure.com",
        AZURE_OPENAI_API_VERSION="2024-02-01",
        AZURE_OPENAI_DEPLOYMENT="gpt",
        attachment_vision_service_enabled=True,
    )
    service = AttachmentVisionService(settings=settings)
    monkeypatch.setattr(
        "app.platform.attachments.services.vision.ephemeral_vision_run",
        AsyncMock(return_value="A bar chart with Q1 revenue rising."),
    )
    monkeypatch.setattr(
        "app.platform.attachments.services.vision.resolve_vision_model_entry",
        lambda **_: type("E", (), {"id": "qwen3.7-plus"})(),
    )

    result = await service.describe(
        data=_TINY_PNG,
        mime_type="image/png",
        filename="chart.png",
        question="What trend is shown?",
    )
    assert result["status"] == "ok"
    assert "bar chart" in str(result["summary"]).lower()
    assert "data_base64" not in result


@pytest.mark.asyncio
async def test_vision_service_disabled_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATTACHMENT_VISION_SERVICE_ENABLED", "false")
    settings = Settings(
        DATABASE_URL="postgresql://x",
        REDIS_URL="redis://x",
        AZURE_API_KEY="k",
        AZURE_OPENAI_BASE_URL="https://example.openai.azure.com",
        AZURE_OPENAI_API_VERSION="2024-02-01",
        AZURE_OPENAI_DEPLOYMENT="gpt",
    )
    service = AttachmentVisionService(settings=settings)
    result = await service.describe(
        data=_TINY_PNG,
        mime_type="image/png",
        filename="chart.png",
        question=None,
    )
    assert result["status"] == "error"
    assert "disabled" in str(result.get("message", "")).lower()


@pytest.mark.asyncio
async def test_analyze_image_tool_returns_summary_not_base64(
    monkeypatch: pytest.MonkeyPatch,
    _image_run_state: None,
) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.tools.pull_tools.load_inline_attachment",
        lambda _chat_id, _attachment_id: _TINY_PNG,
    )
    monkeypatch.setattr(
        "app.platform.attachments.tools.pull_tools.get_attachment_vision_service",
        lambda: AttachmentVisionService(
            settings=Settings(
                DATABASE_URL="postgresql://x",
                REDIS_URL="redis://x",
                AZURE_API_KEY="k",
                AZURE_OPENAI_BASE_URL="https://example.openai.azure.com",
                AZURE_OPENAI_API_VERSION="2024-02-01",
                AZURE_OPENAI_DEPLOYMENT="gpt",
                attachment_vision_service_enabled=True,
            )
        ),
    )
    monkeypatch.setattr(
        "app.platform.attachments.services.vision.ephemeral_vision_run",
        AsyncMock(return_value="Diagram with three boxes labeled API, DB, Cache."),
    )
    monkeypatch.setattr(
        "app.platform.attachments.services.vision.resolve_vision_model_entry",
        lambda **_: type("E", (), {"id": "qwen3.7-plus"})(),
    )

    result = await analyze_image_tool(str(ATTACHMENT_ID), question="Describe architecture")
    assert result["status"] == "ok"
    assert "summary" in result
    assert "data_base64" not in result
    assert "API" in str(result["summary"])


def test_resolve_vision_model_prefers_configured_id(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import yaml

    from app.platform.llm import model_catalog

    catalog_path = tmp_path / "models.yaml"
    catalog_path.write_text(
        yaml.dump(
            {
                "providers": {"dashscope": {"base_url": "https://dashscope.example/v1"}},
                "models": [
                    {
                        "id": "qwen-vl-max",
                        "label": "Qwen VL Max",
                        "provider": "dashscope",
                        "deployment": "qwen-vl-max",
                        "enabled": True,
                        "roles": ["vision_worker"],
                    },
                    {
                        "id": "qwen3.7-plus",
                        "label": "Qwen Chat",
                        "provider": "dashscope",
                        "deployment": "qwen3.7-plus",
                        "enabled": True,
                        "roles": ["chat"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(model_catalog, "_CATALOG_PATH", catalog_path)
    model_catalog.reload_model_catalog()
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("ATTACHMENT_VISION_MODEL_ID", "qwen-vl-max")
    settings = Settings(
        DATABASE_URL="postgresql://x",
        REDIS_URL="redis://x",
        DASHSCOPE_API_KEY="test-key",
        DASHSCOPE_BASE_URL="https://dashscope.example/v1",
    )
    entry = resolve_vision_model_entry(settings=settings)
    assert entry.id == "qwen-vl-max"


def test_resolve_vision_model_ignores_chat_only_env_id(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import yaml

    from app.platform.llm import model_catalog

    catalog_path = tmp_path / "models.yaml"
    catalog_path.write_text(
        yaml.dump(
            {
                "providers": {"dashscope": {"base_url": "https://dashscope.example/v1"}},
                "models": [
                    {
                        "id": "qwen-vl-max",
                        "label": "Qwen VL Max",
                        "provider": "dashscope",
                        "deployment": "qwen-vl-max",
                        "enabled": True,
                        "roles": ["vision_worker"],
                    },
                    {
                        "id": "qwen3.7-plus",
                        "label": "Qwen Chat",
                        "provider": "dashscope",
                        "deployment": "qwen3.7-plus",
                        "enabled": True,
                        "roles": ["chat"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(model_catalog, "_CATALOG_PATH", catalog_path)
    model_catalog.reload_model_catalog()
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("ATTACHMENT_VISION_MODEL_ID", "qwen3.7-plus")
    settings = Settings(
        DATABASE_URL="postgresql://x",
        REDIS_URL="redis://x",
        DASHSCOPE_API_KEY="test-key",
        DASHSCOPE_BASE_URL="https://dashscope.example/v1",
    )
    entry = resolve_vision_model_entry(settings=settings)
    assert entry.id == "qwen-vl-max"

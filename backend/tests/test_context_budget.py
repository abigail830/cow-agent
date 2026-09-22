import uuid

import pytest
from agent_framework import Content, Message

from app.platform.llm.model_catalog import ModelEntry
from app.platform.memory.context_budget import (
    estimate_messages_token_count,
    input_budget_tokens,
)
from app.platform.memory.memory_config import apply_model_compaction_defaults, parse_memory_config


def test_apply_model_compaction_defaults_from_catalog():
    base = parse_memory_config({})
    entry = ModelEntry(
        id="deepseek-flash",
        label="DeepSeek Flash",
        provider="deepseek",
        deployment="deepseek-flash",
        context_window_tokens=1_000_000,
        max_output_tokens=16_384,
    )
    resolved = apply_model_compaction_defaults(base, entry)
    assert resolved.compaction.max_context_window_tokens == 1_000_000
    assert resolved.compaction.max_output_tokens == 16_384
    assert input_budget_tokens(resolved) == 1_000_000 - 16_384


def test_apply_model_compaction_defaults_keeps_profile_when_catalog_missing():
    base = parse_memory_config({"memory": {"compaction": {"max_context_window_tokens": 256_000}}})
    entry = ModelEntry(
        id="gpt-test",
        label="GPT Test",
        provider="azure_openai",
        deployment="gpt-test",
    )
    resolved = apply_model_compaction_defaults(base, entry)
    assert resolved.compaction.max_context_window_tokens == 256_000


def test_estimate_messages_token_count_uses_maf_heuristic():
    messages = [
        Message(role="user", contents=[Content.from_text("hello world" * 20)]),
        Message(role="assistant", contents=[Content.from_text("reply" * 10)]),
    ]
    tokens = estimate_messages_token_count(messages)
    assert tokens > 0


@pytest.mark.asyncio
async def test_reload_catalog_has_1m_for_deepseek_and_qwen37(monkeypatch, tmp_path):
    from pathlib import Path

    import yaml

    from app.platform.llm.model_catalog import reload_model_catalog

    catalog_path = tmp_path / "models.yaml"
    catalog_path.write_text(
        yaml.dump(
            {
                "providers": {"deepseek": {"base_url": "https://example/v1"}},
                "models": [
                    {
                        "id": "deepseek-flash",
                        "label": "DeepSeek Flash",
                        "provider": "deepseek",
                        "deployment": "deepseek-flash",
                        "context_window_tokens": 1_000_000,
                    },
                    {
                        "id": "qwen3.7-plus",
                        "label": "Qwen 3.7 Plus",
                        "provider": "dashscope",
                        "deployment": "qwen3.7-plus",
                        "context_window_tokens": 1_000_000,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.platform.llm.model_catalog._CATALOG_PATH", catalog_path)
    catalog = reload_model_catalog()
    assert catalog.get("deepseek-flash").context_window_tokens == 1_000_000
    assert catalog.get("qwen3.7-plus").context_window_tokens == 1_000_000

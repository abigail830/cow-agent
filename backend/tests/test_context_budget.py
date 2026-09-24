import uuid

import pytest
from agent_framework import Content, Message

from app.platform.llm.model_catalog import ModelEntry
from app.platform.memory.context_budget import (
    estimate_messages_token_count,
    input_budget_tokens,
    prepare_messages_for_usage_estimate,
)
from app.platform.memory.maf_mapping import to_maf_messages
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
async def test_prepare_messages_for_usage_estimate_applies_slim():
    memory_config = apply_model_compaction_defaults(
        parse_memory_config({}),
        ModelEntry(
            id="deepseek-flash",
            label="DeepSeek Flash",
            provider="deepseek",
            deployment="deepseek-flash",
            context_window_tokens=1_000_000,
            max_output_tokens=16_384,
        ),
    )
    rows = [
        {
            "role": "assistant",
            "message_type": "tool_call",
            "content": None,
            "sequence": 1,
            "metadata": {
                "call_id": "c1",
                "tool_name": "hybrid_search",
                "arguments": {"query": "nova " + "x" * 4000},
            },
        },
        {
            "role": "tool",
            "message_type": "tool_result",
            "content": '{"hits": ' + str(list(range(200))) + "}",
            "sequence": 2,
            "metadata": {
                "call_id": "c1",
                "tool_name": "hybrid_search",
                "result": {"hits": 200},
            },
        },
    ]
    raw_messages = to_maf_messages(rows)
    raw_tokens = estimate_messages_token_count(list(raw_messages))

    effective = await prepare_messages_for_usage_estimate(
        list(raw_messages),
        memory_config,
        chat_id=uuid.uuid4(),
        model_id="deepseek-flash",
        model_provider="deepseek",
    )
    effective_tokens = estimate_messages_token_count(effective)

    assert effective_tokens < raw_tokens
    assert effective_tokens / input_budget_tokens(memory_config) < 0.5


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

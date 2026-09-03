import json
import uuid
from typing import Any

from agent_framework import Content, Message

from app.memory.projectors.utils import ensure_dict, stringify_function_call_arguments
from app.platform.attachment_adapters import metadata_attachment_to_maf_content
from app.platform.platform_instructions import RUN_CANCELLED_USER_TEXT

PLATFORM_MESSAGE_TYPE_KEY = "platform_message_type"
PLATFORM_METADATA_KEY = "platform_metadata"


def _platform_props(row: dict[str, Any]) -> dict[str, Any]:
    message_type = row.get("message_type") or ""
    metadata = row.get("metadata") or {}
    if not message_type and not metadata:
        return {}
    return {
        PLATFORM_MESSAGE_TYPE_KEY: message_type,
        PLATFORM_METADATA_KEY: metadata,
    }


def row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "chat_id": str(row.chat_id),
        "role": row.role,
        "content": row.content,
        "message_type": row.message_type,
        "metadata": row.message_metadata or {},
        "parent_id": str(row.parent_id) if row.parent_id else None,
        "sequence": row.sequence,
    }


def _row_to_content(row: dict[str, Any]) -> Content | None:
    message_type = row["message_type"]
    content = row.get("content") or ""
    metadata = row.get("metadata") or {}

    if message_type == "reasoning":
        return Content.from_text_reasoning(
            text=content,
            id=metadata.get("content_id"),
            protected_data=metadata.get("protected_data"),
            additional_properties={
                k: v for k, v in metadata.items() if k not in ("protected_data", "content_id")
            },
        )

    if message_type == "text":
        return Content.from_text(content)

    if message_type in ("tool_call", "mcp_call"):
        return Content.from_function_call(
            call_id=str(metadata.get("call_id") or row.get("id")),
            name=str(metadata.get("tool_name") or metadata.get("name") or "unknown"),
            arguments=stringify_function_call_arguments(metadata.get("arguments")),
        )

    return None


def _attachment_dicts(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    raw = metadata.get("attachments")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _attachments_to_contents(metadata: dict[str, Any], *, chat_id: uuid.UUID) -> list[Content]:
    contents: list[Content] = []
    for item in _attachment_dicts(metadata):
        content = metadata_attachment_to_maf_content(item, chat_id=chat_id)
        if content is not None:
            contents.append(content)
    return contents


def to_maf_messages(rows: list[dict[str, Any]]) -> list[Message]:
    """Rebuild MAF history with Anthropic-compatible grouping.

    Assistant text/tool_use blocks are coalesced into one assistant message.
    Tool results immediately follow as separate tool-role messages.
    Duplicate tool rows (audit + persist) are skipped by call_id.
    """
    messages: list[Message] = []
    assistant_contents: list[Content] = []
    seen_tool_calls: set[str] = set()
    seen_tool_results: set[str] = set()

    pending_assistant_meta: dict[str, Any] = {}

    def flush_assistant() -> None:
        nonlocal assistant_contents, pending_assistant_meta
        if assistant_contents:
            props = (
                {
                    PLATFORM_MESSAGE_TYPE_KEY: pending_assistant_meta.get("message_type"),
                    PLATFORM_METADATA_KEY: pending_assistant_meta.get("metadata") or {},
                }
                if pending_assistant_meta.get("message_type")
                else {}
            )
            messages.append(
                Message(role="assistant", contents=list(assistant_contents), additional_properties=props)
            )
            assistant_contents = []
            pending_assistant_meta = {}

    for row in rows:
        message_type = row["message_type"]
        role = row["role"]
        metadata = row.get("metadata") or {}
        call_id = str(metadata.get("call_id") or "")

        if message_type == "text" and role == "user":
            flush_assistant()
            user_contents: list[Content] = []
            text = row.get("content") or ""
            if text:
                user_contents.append(Content.from_text(text))
            if _attachment_dicts(metadata):
                chat_id_raw = row.get("chat_id")
                if chat_id_raw:
                    user_contents.extend(
                        _attachments_to_contents(metadata, chat_id=uuid.UUID(str(chat_id_raw)))
                    )
            if not user_contents:
                user_contents.append(Content.from_text(""))
            messages.append(
                Message(
                    role="user",
                    contents=user_contents,
                    additional_properties=_platform_props(row),
                )
            )
            continue

        if message_type == "run_cancelled":
            flush_assistant()
            text = row.get("content") or RUN_CANCELLED_USER_TEXT
            messages.append(Message(role="user", contents=[Content.from_text(text)]))
            continue

        if message_type == "cancelled":
            original = metadata.get("original_type", "text")
            content = row.get("content") or ""
            if original == "reasoning":
                label = "[Cancelled partial reasoning]"
            else:
                label = "[Cancelled partial response]"
            text = f"{label} {content}".strip() if content else label
            assistant_contents.append(Content.from_text(text))
            continue

        if message_type in ("tool_result", "mcp_result"):
            if call_id and call_id in seen_tool_results:
                continue
            if call_id:
                seen_tool_results.add(call_id)

            flush_assistant()
            if metadata.get("memory_slimmed"):
                result = row.get("content") or ""
            else:
                result = metadata.get("result", row.get("content"))
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)
            messages.append(
                Message(
                    role="tool",
                    contents=[
                        Content.from_function_result(
                            call_id=str(call_id or row.get("id")),
                            result=result,
                        )
                    ],
                    additional_properties=_platform_props(row),
                )
            )
            continue

        if message_type.startswith("skill_"):
            flush_assistant()
            messages.append(
                Message(
                    role="tool",
                    contents=[Content.from_text(row.get("content") or json.dumps(metadata, ensure_ascii=False))],
                    additional_properties=_platform_props(row),
                )
            )
            continue

        if message_type == "error":
            flush_assistant()
            messages.append(
                Message(role="assistant", contents=[Content.from_text(f"[error] {row.get('content')}")])
            )
            continue

        if message_type in ("text", "reasoning", "tool_call", "mcp_call") and role == "assistant":
            if message_type in ("tool_call", "mcp_call"):
                if call_id and call_id in seen_tool_calls:
                    continue
                if call_id:
                    seen_tool_calls.add(call_id)

            if message_type == "reasoning" and not metadata.get("protected_data"):
                content = Content.from_text(row.get("content") or "")
            else:
                content = _row_to_content(row)
            if content is not None:
                if message_type in ("tool_call", "mcp_call") and not pending_assistant_meta:
                    pending_assistant_meta = {"message_type": message_type, "metadata": metadata}
                assistant_contents.append(content)
            continue

    flush_assistant()
    return messages


def maf_messages_to_projection_rows(messages: list[Message]) -> list[dict[str, Any]]:
    """Expand MAF messages into platform row dicts for HistoryProjection."""
    rows: list[dict[str, Any]] = []
    seq = 0
    call_names: dict[str, str] = {}

    for message in messages:
        props = message.additional_properties or {}
        platform_type = props.get(PLATFORM_MESSAGE_TYPE_KEY)
        platform_metadata = dict(props.get(PLATFORM_METADATA_KEY) or {})

        for content in message.contents or []:
            seq += 1
            content_type = getattr(content, "type", None)

            if message.role == "user":
                rows.append(
                    {
                        "role": "user",
                        "message_type": platform_type or "text",
                        "content": getattr(content, "text", None) or "",
                        "metadata": platform_metadata,
                        "sequence": seq,
                    }
                )
                continue

            if message.role == "assistant":
                if content_type == "text_reasoning":
                    rows.append(
                        {
                            "role": "assistant",
                            "message_type": "reasoning",
                            "content": getattr(content, "text", None) or "",
                            "metadata": platform_metadata,
                            "sequence": seq,
                        }
                    )
                elif content_type == "function_call":
                    call_id = str(getattr(content, "call_id", "") or "")
                    tool_name = str(getattr(content, "name", "") or "unknown")
                    if call_id:
                        call_names[call_id] = tool_name
                    rows.append(
                        {
                            "role": "assistant",
                            "message_type": platform_type or "tool_call",
                            "content": None,
                            "metadata": {
                                **platform_metadata,
                                "call_id": call_id or None,
                                "tool_name": tool_name,
                                "arguments": ensure_dict(getattr(content, "arguments", {})),
                            },
                            "sequence": seq,
                        }
                    )
                else:
                    rows.append(
                        {
                            "role": "assistant",
                            "message_type": platform_type or "text",
                            "content": getattr(content, "text", None) or str(content),
                            "metadata": platform_metadata,
                            "sequence": seq,
                        }
                    )
                continue

            if message.role == "tool":
                if content_type == "function_result":
                    call_id = str(getattr(content, "call_id", "") or "")
                    tool_name = platform_metadata.get("tool_name") or call_names.get(call_id)
                    result = getattr(content, "result", None)
                    rows.append(
                        {
                            "role": "tool",
                            "message_type": platform_type or "tool_result",
                            "content": result if isinstance(result, str) else json.dumps(result, ensure_ascii=False),
                            "metadata": {
                                **platform_metadata,
                                "call_id": call_id or None,
                                "tool_name": tool_name,
                                "result": result,
                            },
                            "sequence": seq,
                        }
                    )
                else:
                    rows.append(
                        {
                            "role": "tool",
                            "message_type": platform_type or "skill_load",
                            "content": getattr(content, "text", None) or "",
                            "metadata": platform_metadata,
                            "sequence": seq,
                        }
                    )

    return rows


def _row_to_maf_message(row: dict[str, Any]) -> Message | None:
    """Single-row conversion (used by tests or legacy paths)."""
    rebuilt = to_maf_messages([row])
    return rebuilt[0] if rebuilt else None


def maf_message_to_rows(
    chat_id: str,
    message: Message,
    *,
    start_sequence: int,
    call_names: dict[str, str] | None = None,
    call_arguments: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Convert a MAF Message into one or more DB row dicts."""
    rows: list[dict[str, Any]] = []
    seq = start_sequence

    platform_type = (message.additional_properties or {}).get("platform_message_type")
    for content in message.contents or []:
        if getattr(content, "type", None) == "text_reasoning" or platform_type == "reasoning":
            meta = dict(getattr(content, "additional_properties", None) or {})
            protected = getattr(content, "protected_data", None)
            if protected:
                meta["protected_data"] = protected
            content_id = getattr(content, "id", None)
            if content_id:
                meta["content_id"] = content_id
            rows.append(
                {
                    "chat_id": chat_id,
                    "role": "assistant",
                    "message_type": "reasoning",
                    "content": getattr(content, "text", None) or "",
                    "metadata": meta,
                    "sequence": seq,
                }
            )
            seq += 1
            continue

        if getattr(content, "type", None) == "function_call":
            call_id = getattr(content, "call_id", None)
            call_id_str = str(call_id) if call_id is not None else ""
            arguments = ensure_dict(getattr(content, "arguments", {}))
            if call_arguments and call_id_str in call_arguments:
                arguments = call_arguments[call_id_str]
            rows.append(
                {
                    "chat_id": chat_id,
                    "role": "assistant",
                    "message_type": "tool_call",
                    "content": None,
                    "metadata": {
                        "call_id": call_id,
                        "tool_name": getattr(content, "name", None),
                        "arguments": arguments,
                    },
                    "sequence": seq,
                }
            )
            seq += 1
            continue

        if getattr(content, "type", None) == "function_result":
            call_id = getattr(content, "call_id", None)
            call_id_str = str(call_id) if call_id is not None else ""
            tool_name = (call_names or {}).get(call_id_str)
            rows.append(
                {
                    "chat_id": chat_id,
                    "role": "tool",
                    "message_type": "tool_result",
                    "content": getattr(content, "result", None),
                    "metadata": {
                        "call_id": call_id,
                        "tool_name": tool_name,
                        "arguments": (call_arguments or {}).get(call_id_str, {}),
                        "result": getattr(content, "result", None),
                    },
                    "sequence": seq,
                }
            )
            seq += 1
            continue

        text = content.text if hasattr(content, "text") else str(content)
        rows.append(
            {
                "chat_id": chat_id,
                "role": message.role,
                "message_type": "text",
                "content": text,
                "metadata": {},
                "sequence": seq,
            }
        )
        seq += 1

    if not rows and message.role:
        rows.append(
            {
                "chat_id": chat_id,
                "role": message.role,
                "message_type": "text",
                "content": "",
                "metadata": {},
                "sequence": start_sequence,
            }
        )
    return rows

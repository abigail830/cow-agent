"""Project chat_messages + ui_annotations to API shapes."""

from __future__ import annotations

import uuid
from typing import Any

from app.db.models import ChatMessage, ChatRun, ChatUiAnnotation
from app.platform.memory.maf_mapping import maf_message_to_rows
from app.platform.memory.message_validate import message_from_body

# Sub-ordering within one MAF message row (max 99 content blocks per message).
_SEQUENCE_SCALE = 100


def display_sequence(base_sequence: int, index: int = 0) -> int:
    """Map chat_messages.sequence to UI ordering (sub-blocks use index > 0)."""
    return int(base_sequence) * _SEQUENCE_SCALE + index


def platform_dict_from_message(message: ChatMessage) -> dict[str, Any]:
    body = message.body if isinstance(message.body, dict) else {}
    props = body.get("additional_properties") or {}
    platform = props.get("platform") if isinstance(props, dict) else None
    return platform if isinstance(platform, dict) else {}


def turn_ui_timeline_anchors(messages: list[ChatMessage]) -> dict[uuid.UUID, uuid.UUID]:
    """Map turn_id → anchor message id when a turn stores interleaved ui_timeline."""
    anchors: dict[uuid.UUID, uuid.UUID] = {}
    for message in messages:
        if message.role != "assistant":
            continue
        if platform_dict_from_message(message).get("ui_timeline"):
            anchors.setdefault(message.turn_id, message.id)
    return anchors


def _expand_ui_timeline_rows(message: ChatMessage, timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    created_at = message.created_at.isoformat() if message.created_at else None
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(timeline):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        base = {
            "id": f"{message.id}:{index}",
            "chat_id": str(message.chat_id),
            "parent_id": str(message.id),
            "sequence": display_sequence(message.sequence, index),
            "turn_id": str(message.turn_id),
            "created_at": created_at,
        }
        if kind == "reasoning":
            rows.append(
                {
                    **base,
                    "role": "assistant",
                    "message_type": "reasoning",
                    "content": str(item.get("content") or ""),
                    "metadata": metadata,
                }
            )
            continue
        if kind == "text":
            rows.append(
                {
                    **base,
                    "role": "assistant",
                    "message_type": "text",
                    "content": str(item.get("content") or ""),
                    "metadata": metadata,
                }
            )
            continue
        if kind in {"tool_call", "mcp_call"}:
            rows.append(
                {
                    **base,
                    "role": "assistant",
                    "message_type": "tool_call",
                    "content": None,
                    "metadata": metadata,
                }
            )
            continue
        if kind == "tool_result":
            rows.append(
                {
                    **base,
                    "role": "tool",
                    "message_type": "tool_result",
                    "content": item.get("content"),
                    "metadata": metadata,
                }
            )
            continue
        if kind == "artifact":
            spec = metadata.get("spec") if isinstance(metadata.get("spec"), dict) else {}
            title = spec.get("title") or item.get("content") or spec.get("artifact_id") or "artifact"
            rows.append(
                {
                    **base,
                    "role": "assistant",
                    "message_type": "artifact",
                    "content": title,
                    "metadata": metadata,
                }
            )
            continue
        if kind == "viz":
            spec = metadata.get("spec") if isinstance(metadata.get("spec"), dict) else {}
            title = spec.get("title") or item.get("content") or "viz"
            rows.append(
                {
                    **base,
                    "role": "assistant",
                    "message_type": "viz",
                    "content": title,
                    "metadata": metadata,
                }
            )
    return rows


def expand_message_to_platform_rows(message: ChatMessage) -> list[dict[str, Any]]:
    """Expand one MAF Message row into legacy platform MessageOut rows for UI."""
    ui_timeline = platform_dict_from_message(message).get("ui_timeline")
    if isinstance(ui_timeline, list) and ui_timeline:
        expanded = _expand_ui_timeline_rows(message, ui_timeline)
        if expanded:
            return expanded

    maf = message_from_body(message.body)
    rows = maf_message_to_rows(
        str(message.chat_id),
        maf,
        start_sequence=message.sequence,
    )
    created_at = message.created_at.isoformat() if message.created_at else None
    if not rows:
        return [
            {
                "id": str(message.id),
                "chat_id": str(message.chat_id),
                "role": message.role,
                "message_type": "text",
                "content": "",
                "metadata": {},
                "parent_id": None,
                "sequence": display_sequence(message.sequence, 0),
                "turn_id": str(message.turn_id),
                "created_at": created_at,
            }
        ]
    expanded: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        expanded.append(
            {
                "id": f"{message.id}:{index}",
                "chat_id": str(message.chat_id),
                "role": row["role"],
                "message_type": row["message_type"],
                "content": row.get("content"),
                "metadata": row.get("metadata") or {},
                "parent_id": str(message.id),
                "sequence": display_sequence(message.sequence, index),
                "turn_id": str(message.turn_id),
                "maf_message_id": str(message.id),
                "created_at": created_at,
            }
        )
    return expanded


def annotation_to_platform_row(annotation: ChatUiAnnotation) -> dict[str, Any]:
    display = annotation.display if isinstance(annotation.display, dict) else {}
    kind = annotation.kind
    message_type = kind if kind in {"viz", "artifact", "fulfillment"} else kind
    title = display.get("title")
    if title is None and isinstance(display.get("spec"), dict):
        title = display["spec"].get("title")
    metadata: dict[str, Any]
    if kind == "viz" and "spec" in display:
        metadata = {"spec": display["spec"]}
    elif kind == "artifact" and "spec" in display:
        metadata = {"spec": display["spec"]}
    else:
        metadata = dict(display)
        metadata.setdefault("ref", annotation.ref)
    return {
        "id": str(annotation.id),
        "chat_id": str(annotation.chat_id),
        "role": "assistant",
        "message_type": message_type,
        "content": title or annotation.ref,
        "metadata": metadata,
        "parent_id": str(annotation.anchor_message_id) if annotation.anchor_message_id else None,
        "sequence": display_sequence(annotation.sequence, 0),
        "turn_id": str(annotation.turn_id),
        "created_at": annotation.created_at.isoformat() if annotation.created_at else None,
    }


def run_to_platform_row(run: ChatRun, *, sequence: int) -> dict[str, Any]:
    created_at = run.finished_at.isoformat() if run.finished_at else run.started_at.isoformat() if run.started_at else None
    if run.status == "cancelled":
        from app.platform.agent.platform_instructions import RUN_CANCELLED_USER_TEXT

        return {
            "id": f"run-cancel-{run.id}",
            "chat_id": str(run.chat_id),
            "role": "user",
            "message_type": "run_cancelled",
            "content": RUN_CANCELLED_USER_TEXT,
            "metadata": {"run_id": str(run.id), "cancelled_by": "user"},
            "parent_id": None,
            "sequence": sequence,
            "turn_id": str(run.user_message_id) if run.user_message_id else None,
            "created_at": created_at,
        }
    if run.status == "failed" and run.error:
        return {
            "id": f"run-error-{run.id}",
            "chat_id": str(run.chat_id),
            "role": "assistant",
            "message_type": "error",
            "content": run.error[:4000],
            "metadata": {"run_id": str(run.id)},
            "parent_id": None,
            "sequence": sequence,
            "turn_id": str(run.user_message_id) if run.user_message_id else None,
            "created_at": created_at,
        }
    raise ValueError(f"Run {run.id} is not a displayable terminal status: {run.status}")


def _turn_max_sequence(rows: list[dict[str, Any]], turn_id: str) -> int | None:
    turn_rows = [row for row in rows if str(row.get("turn_id") or "") == turn_id]
    if not turn_rows:
        return None
    return max(int(row["sequence"]) for row in turn_rows)


def merge_timeline_to_message_outs(
    *,
    chat_id: uuid.UUID,
    messages: list[ChatMessage],
    annotations: list[ChatUiAnnotation],
    runs: list[ChatRun] | None = None,
    include_run_markers: bool = False,
) -> list[dict[str, Any]]:
    """Merge messages and ui_annotations by sequence into flat MessageOut list."""
    ui_timeline_turns = turn_ui_timeline_anchors(messages)
    items: list[tuple[int, str, Any]] = []
    for message in messages:
        if message.turn_id in ui_timeline_turns and message.id != ui_timeline_turns[message.turn_id]:
            continue
        items.append((int(message.sequence), "message", message))
    for annotation in annotations:
        if annotation.turn_id in ui_timeline_turns:
            continue
        items.append((int(annotation.sequence), "annotation", annotation))

    items.sort(key=lambda item: item[0])
    outs: list[dict[str, Any]] = []
    for _, kind, payload in items:
        if kind == "message":
            outs.extend(expand_message_to_platform_rows(payload))
        else:
            outs.append(annotation_to_platform_row(payload))

    if include_run_markers and runs:
        message_turn_by_id = {str(message.id): str(message.turn_id) for message in messages}
        for run in runs:
            if run.status not in {"cancelled", "failed"}:
                continue
            if run.user_message_id is None:
                continue
            turn_id = message_turn_by_id.get(str(run.user_message_id))
            if turn_id is None:
                continue
            max_seq = _turn_max_sequence(outs, turn_id)
            if max_seq is None:
                continue
            outs.append(run_to_platform_row(run, sequence=max_seq + 1))

    outs.sort(key=lambda row: int(row["sequence"]))
    return outs


def build_turn_message_outs(
    chat_id: uuid.UUID,
    user_message: ChatMessage | None,
    turn_messages: list[ChatMessage],
    turn_annotations: list[ChatUiAnnotation] | None = None,
) -> list[dict[str, Any]]:
    """Build done-event message list for one turn."""
    items: list[ChatMessage] = []
    if user_message is not None:
        items.append(user_message)
    seen = {m.id for m in items}
    for message in turn_messages:
        if message.id not in seen:
            items.append(message)
            seen.add(message.id)
    return merge_timeline_to_message_outs(
        chat_id=chat_id,
        messages=items,
        annotations=turn_annotations or [],
        include_run_markers=False,
    )


def chat_message_to_maf_out(message: ChatMessage) -> dict[str, Any]:
    return {
        "kind": "message",
        "id": str(message.id),
        "sequence": int(message.sequence),
        "turn_id": str(message.turn_id),
        "message": message.body,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def build_timeline_response(
    *,
    chat_id: uuid.UUID,
    messages: list[ChatMessage],
    annotations: list[ChatUiAnnotation],
    runs: list[ChatRun] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    ui_timeline_turns = turn_ui_timeline_anchors(messages)
    merged: list[tuple[int, str, Any]] = []
    for message in messages:
        if message.turn_id in ui_timeline_turns and message.id != ui_timeline_turns[message.turn_id]:
            continue
        merged.append((int(message.sequence), "message", message))
    for annotation in annotations:
        if annotation.turn_id in ui_timeline_turns:
            continue
        merged.append((int(annotation.sequence), "annotation", annotation))
    merged.sort(key=lambda item: item[0])

    for _, kind, payload in merged:
        if kind == "message":
            items.append(chat_message_to_maf_out(payload))
        else:
            items.append(
                {
                    "kind": "ui_annotation",
                    "id": str(payload.id),
                    "sequence": int(payload.sequence),
                    "turn_id": str(payload.turn_id),
                    "annotation": {
                        "kind": payload.kind,
                        "ref": payload.ref,
                        "display": payload.display or {},
                        "anchor_message_id": str(payload.anchor_message_id)
                        if payload.anchor_message_id
                        else None,
                    },
                    "created_at": payload.created_at.isoformat() if payload.created_at else None,
                }
            )

    run_outs = []
    if runs:
        for run in runs:
            run_outs.append(
                {
                    "id": str(run.id),
                    "status": run.status,
                    "error": run.error,
                    "user_message_id": str(run.user_message_id) if run.user_message_id else None,
                    "model_id": run.model_id,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                }
            )

    return {
        "chat_id": str(chat_id),
        "items": items,
        "runs": run_outs,
    }

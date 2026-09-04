from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from agent_framework import MiddlewareTermination
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentModel, Chat, Message
from app.db.repositories.attachments import AttachmentRepository
from app.db.repositories.messages import MessageRepository
from app.platform.memory.long_term import try_handle_memory_command
from app.platform.memory.maf_mapping import maf_message_to_rows
from app.platform.memory.memory_config import MemoryConfig, parse_memory_config
from app.platform.agent.agent_factory import AgentFactory
from app.platform.mcp.mcp_connect import disconnect_bundle, iter_mcp_connect_keepalive
from app.platform.agent.platform_instructions import RUN_CANCELLED_USER_TEXT
from app.platform.session.session_store import SessionStore
from app.platform.session.user_message_input import build_user_run_input, link_attachments_metadata
from app.platform.attachments.service import AttachmentService
from app.platform.llm.stream_errors import user_facing_stream_error
from app.platform.chat.run_manager import get_run_manager
from app.platform.agent.plugin_registry import (
    run_plugin_end,
    run_plugin_finalize_failure,
    run_plugin_finalize_success,
    run_plugin_start,
)
from app.platform.runtime.plugin import RunContext
from app.platform.chat.stream_pipeline import (
    collect_stream_emitters,
    drain_remaining_stream_events,
    drain_stream_events,
    tool_result_stream_events,
)
from app.agent_specific.proposal.stream_emitter import proposal_updated_event
from app.agent_specific.slide.stream_emitter import (
    SlideBuildStreamEmitter,
    flush_completed_slide_build_artifacts,
)
from app.agent_specific.viz.stream_emitter import VizStreamEmitter, viz_spec_payload
from app.shared.artifacts.stream_emitter import ArtifactStreamEmitter, artifact_spec_payload
from app.agent_specific.diagram.context import get_run_diagram_state
from app.shared.artifacts.context import get_run_artifact_state
from app.agent_specific.proposal.context import get_run_proposal_state
from app.agent_specific.proposal.artifact_spec import ArtifactSpec
from app.agent_specific.viz.context import get_run_viz_state, init_run_viz_state, reset_run_viz_state
from app.agent_specific.viz.spec import VizSpec

logger = logging.getLogger(__name__)

_TOOL_ROW_TYPES = frozenset({"tool_call", "tool_result", "mcp_call", "mcp_result"})


class ChatRunService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._messages = MessageRepository(db)
        self._sessions = SessionStore(db)
        self._factory = AgentFactory(db)

    async def _get_chat(self, chat_id: uuid.UUID) -> Chat:
        result = await self._db.execute(select(Chat).where(Chat.id == chat_id))
        chat = result.scalar_one_or_none()
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")
        return chat

    async def _maybe_set_chat_title(self, chat: Chat, content: str, attachments: list | None = None) -> None:
        if chat.title and chat.title != "New Chat":
            return
        snippet = " ".join(content.strip().split())[:60]
        if not snippet and attachments:
            snippet = attachments[0].filename[:60]
        if snippet:
            chat.title = snippet

    async def _resolve_attachments(self, chat: Chat, attachment_ids: list[uuid.UUID]) -> list:
        if not attachment_ids:
            return []
        agent = await self._db.get(AgentModel, chat.agent_id)
        if agent is None:
            raise ValueError("Agent not found for chat")
        service = AttachmentService(self._db)
        return await service.resolve_for_message(
            chat.id,
            attachment_ids,
            expected_provider=agent.model_provider,
        )

    async def _commit_user_turn(
        self,
        chat: Chat,
        content: str,
        *,
        attachments: list | None = None,
        attachment_ids: list[uuid.UUID] | None = None,
    ) -> Message:
        """Persist the user message immediately so it survives agent failures."""
        resolved = (
            attachments
            if attachments is not None
            else await self._resolve_attachments(chat, attachment_ids or [])
        )
        metadata = link_attachments_metadata({}, resolved)
        row = await self._messages.insert(
            chat_id=chat.id,
            role="user",
            message_type="text",
            content=content,
            metadata=metadata or None,
        )
        if resolved:
            await AttachmentRepository(self._db).link_to_message(
                [att.id for att in resolved],
                row.id,
            )
        await self._maybe_set_chat_title(chat, content, resolved)
        await self._db.commit()
        return row

    async def _ensure_db_connection(self) -> None:
        """Re-open the request session if Postgres closed it during a long agent run."""
        try:
            await self._db.execute(text("SELECT 1"))
        except DBAPIError as exc:
            message = str(exc).lower()
            if "connection is closed" not in message and "interfaceerror" not in message:
                raise
            logger.warning("Refreshing stale DB connection before persist: %s", exc)
            await self._db.rollback()
            conn = await self._db.connection()
            await conn.invalidate()
            await self._db.execute(text("SELECT 1"))

    async def _finalize_cancel(
        self,
        chat_id: uuid.UUID,
        run_id: uuid.UUID,
        accumulator: "_StreamTurnAccumulator",
    ) -> None:
        """Persist partial assistant output and a user-visible cancellation marker."""
        try:
            if accumulator.has_content():
                await accumulator.persist_cancelled(self._messages, chat_id, run_id)
            await self._messages.insert(
                chat_id=chat_id,
                role="user",
                message_type="run_cancelled",
                content=RUN_CANCELLED_USER_TEXT,
                metadata={"run_id": str(run_id), "cancelled_by": "user"},
            )
            await self._db.commit()
        except Exception:
            logger.exception("Failed to persist cancelled turn for chat %s", chat_id)
            await self._db.rollback()

    async def _memory_config_for_chat(self, chat: Chat) -> MemoryConfig:
        agent = await self._db.get(AgentModel, chat.agent_id)
        return parse_memory_config(agent.config if agent else {})

    async def _agent_slug_for_chat(self, chat: Chat) -> str | None:
        agent = await self._db.get(AgentModel, chat.agent_id)
        return agent.slug if agent else None

    async def _build_run_context(self, chat: Chat) -> RunContext:
        return RunContext(
            db=self._db,
            chat=chat,
            chat_id=chat.id,
            session_store=self._sessions,
            agent_slug=await self._agent_slug_for_chat(chat),
        )

    async def _prepare_run_plugins(self, chat: Chat) -> RunContext:
        ctx = await self._build_run_context(chat)
        await run_plugin_start(ctx)
        init_run_viz_state()
        return ctx

    async def _finalize_success(
        self,
        chat_id: uuid.UUID,
        session: Any,
        response: Any,
        *,
        memory_config: MemoryConfig,
        turn_start_sequence: int,
        run_ctx: RunContext | None = None,
        accumulator: "_StreamTurnAccumulator | None" = None,
    ) -> None:
        if accumulator is not None and accumulator.has_content():
            accumulator.enrich_tool_arguments_from_response(response)
            await accumulator.persist(self._messages, chat_id)
        else:
            await self._persist_agent_messages(chat_id, response, skip_tool_rows=False)
        if run_ctx is not None:
            await run_plugin_finalize_success(run_ctx, accumulator=accumulator)
        await self._sessions.append_completed_turn(
            chat_id,
            memory_config,
            turn_start_sequence=turn_start_sequence,
        )
        await self._sessions.save_session(chat_id, session)
        await self._db.commit()

    async def _finalize_failure(
        self,
        chat_id: uuid.UUID,
        exc: Exception,
        *,
        response: Any | None = None,
        run_ctx: RunContext | None = None,
        accumulator: "_StreamTurnAccumulator | None" = None,
    ) -> None:
        """Best-effort persist of partial assistant output plus an error row."""
        try:
            if response is not None:
                await self._persist_agent_messages(chat_id, response)
            elif accumulator is not None and accumulator.has_content():
                await accumulator.persist(self._messages, chat_id)
            if run_ctx is not None:
                await run_plugin_finalize_failure(run_ctx, accumulator=accumulator)
            await self._persist_run_error(chat_id, exc)
            await self._db.commit()
        except Exception:
            logger.exception("Failed to persist partial turn for chat %s", chat_id)
            await self._db.rollback()

    async def _persist_run_error(self, chat_id: uuid.UUID, exc: Exception) -> None:
        message = user_facing_stream_error(exc)
        await self._messages.insert(
            chat_id=chat_id,
            role="assistant",
            message_type="error",
            content=message[:4000],
            metadata={"error_type": type(exc).__name__},
        )
        await self._db.flush()

    async def _persist_pending_artifacts(self, chat_id: uuid.UUID) -> None:
        specs: list[ArtifactSpec] = []
        proposal_ctx = get_run_proposal_state()
        if proposal_ctx is not None:
            specs.extend(proposal_ctx.drain_pending_artifacts())
        diagram_ctx = get_run_diagram_state()
        if diagram_ctx is not None:
            specs.extend(diagram_ctx.drain_pending_artifacts())
        slide_ctx = get_run_artifact_state()
        if slide_ctx is not None:
            specs.extend(slide_ctx.drain_pending_artifacts())
        for spec in specs:
            await self._messages.insert(
                chat_id=chat_id,
                role="assistant",
                message_type="artifact",
                content=spec.title,
                metadata={"spec": artifact_spec_payload(spec)},
            )

    async def run_message(
        self,
        chat_id: uuid.UUID,
        content: str,
        *,
        attachment_ids: list[uuid.UUID] | None = None,
    ) -> str:
        chat = await self._get_chat(chat_id)
        memory_config = await self._memory_config_for_chat(chat)
        session = await self._sessions.get_or_create(chat_id)
        run_ctx = await self._prepare_run_plugins(chat)
        attachments = await self._resolve_attachments(chat, attachment_ids or [])
        if not content.strip() and not attachments:
            raise ValueError("Message content or attachments required")
        user_row = await self._commit_user_turn(
            chat, content, attachments=attachments, attachment_ids=attachment_ids
        )
        run_input = build_user_run_input(content, attachments)
        memory_result = await try_handle_memory_command(
            self._db,
            user_id=chat.user_id,
            agent_id=chat.agent_id,
            content=content,
        )
        if memory_result and memory_result.handled:
            if memory_result.is_pure_command:
                await self._messages.insert(
                    chat_id=chat_id,
                    role="assistant",
                    message_type="text",
                    content=memory_result.confirmation,
                    metadata={"source": "memory_command"},
                )
            await self._db.commit()
            if memory_result.is_pure_command:
                reset_run_viz_state()
                await run_plugin_end(run_ctx)
                return memory_result.confirmation

        bundle = await self._factory.build(
            chat.agent_id,
            chat_id=chat_id,
            user_id=chat.user_id,
            turn_start_sequence=user_row.sequence,
            session_store=self._sessions,
        )
        try:
            async with bundle as agent:
                result = await agent.run(run_input, session=session)
            from app.config import get_settings
            from app.agent_specific.slide.build_jobs import wait_for_slide_build_jobs

            settings = get_settings()
            if settings.sandbox_async_build:
                wait_for_slide_build_jobs(
                    chat_id,
                    timeout_seconds=max(60.0, settings.sandbox_timeout_seconds + 30.0),
                )
            flush_completed_slide_build_artifacts(chat_id)
            await self._persist_pending_artifacts(chat_id)
            await self._finalize_success(
                chat_id,
                session,
                result,
                memory_config=memory_config,
                turn_start_sequence=user_row.sequence,
                run_ctx=run_ctx,
            )
            return result.text or ""
        except Exception as exc:
            await self._finalize_failure(chat_id, exc, run_ctx=run_ctx)
            raise
        finally:
            reset_run_viz_state()
            await run_plugin_end(run_ctx)

    async def stream_message(
        self,
        chat_id: uuid.UUID,
        content: str,
        *,
        attachment_ids: list[uuid.UUID] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        chat = await self._get_chat(chat_id)
        memory_config = await self._memory_config_for_chat(chat)
        session = await self._sessions.get_or_create(chat_id)
        run_ctx = await self._prepare_run_plugins(chat)
        attachments = await self._resolve_attachments(chat, attachment_ids or [])
        if not content.strip() and not attachments:
            raise ValueError("Message content or attachments required")
        user_row = await self._commit_user_turn(
            chat, content, attachments=attachments, attachment_ids=attachment_ids
        )
        run_input = build_user_run_input(content, attachments)
        memory_result = await try_handle_memory_command(
            self._db,
            user_id=chat.user_id,
            agent_id=chat.agent_id,
            content=content,
        )
        if memory_result and memory_result.handled:
            if memory_result.is_pure_command:
                await self._messages.insert(
                    chat_id=chat_id,
                    role="assistant",
                    message_type="text",
                    content=memory_result.confirmation,
                    metadata={"source": "memory_command"},
                )
            await self._db.commit()
            yield {
                "event": "memory_updated",
                "data": memory_result.to_dict(),
            }
            if memory_result.is_pure_command:
                reset_run_viz_state()
                await run_plugin_end(run_ctx)
                yield {"event": "done", "data": {"text": memory_result.confirmation}}
                return

        run_manager = get_run_manager()
        run = await run_manager.start_run(chat_id, user_row.id)
        run_ctx.run_id = run.run_id
        stream_emitters = collect_stream_emitters(run_ctx.agent_slug)
        accumulator = _StreamTurnAccumulator()

        emitter = _StreamSseEmitter(
            chat_id,
            stream_emitters=stream_emitters,
            accumulator=accumulator,
        )

        async def finalize_cancel_once() -> None:
            await self._finalize_cancel(chat_id, run.run_id, accumulator)

        await run_manager.register_finalize(run.run_id, finalize_cancel_once)
        yield {
            "event": "run_started",
            "data": {
                "run_id": str(run.run_id),
                "chat_id": str(chat_id),
                "user_message_id": str(user_row.id),
            },
        }

        final: Any | None = None

        async def _emit_cancelled() -> AsyncIterator[dict[str, Any]]:
            await run_manager.finalize_cancelled(run.run_id)
            yield {
                "event": "run_cancelled",
                "data": {"run_id": str(run.run_id), "chat_id": str(chat_id)},
            }

        try:
            bundle = await self._factory.build(
                chat.agent_id,
                chat_id=chat_id,
                user_id=chat.user_id,
                stop_event=run.stop_event,
                turn_start_sequence=user_row.sequence,
                session_store=self._sessions,
            )
            async for keepalive in iter_mcp_connect_keepalive(bundle):
                yield keepalive
            agent = bundle.agent
            try:
                stream = agent.run(run_input, session=session, stream=True)
                async for update in stream:
                    if run.stop_event.is_set():
                        break
                    accumulator.observe(update)
                    for event in emitter.emit(update):
                        yield event
                    # Emit charts as soon as SQL/suggest_visualization completes so order
                    # follows the agent stream (text ↔ tools ↔ viz interleave naturally).
                    for event in drain_stream_events(stream_emitters, chat_id, accumulator):
                        yield event

                for event in emitter.flush():
                    yield event
                for event in drain_stream_events(stream_emitters, chat_id, accumulator):
                    yield event

                async for event in drain_remaining_stream_events(stream_emitters, chat_id, accumulator):
                    yield event

                if run.stop_event.is_set():
                    async for event in _emit_cancelled():
                        yield event
                    return

                final = await stream.get_final_response()
            finally:
                await disconnect_bundle(bundle)

            # Unlock client UI before DB/session persistence (can take seconds on tool-heavy turns).
            yield {
                "event": "stream_idle",
                "data": {"chat_id": str(chat_id), "run_id": str(run.run_id)},
            }

            await self._ensure_db_connection()
            await self._finalize_success(
                chat_id,
                session,
                final,
                memory_config=memory_config,
                turn_start_sequence=user_row.sequence,
                run_ctx=run_ctx,
                accumulator=accumulator,
            )
            preview_event = proposal_updated_event(chat_id)
            if preview_event is not None:
                yield preview_event
            yield {"event": "done", "data": {"text": final.text or ""}}
        except MiddlewareTermination:
            if run.stop_event.is_set():
                async for event in _emit_cancelled():
                    yield event
                return
            raise
        except asyncio.CancelledError:
            if run.stop_event.is_set():
                async for event in _emit_cancelled():
                    yield event
                return
            raise
        except Exception as exc:
            if run.stop_event.is_set():
                async for event in _emit_cancelled():
                    yield event
                return
            await self._ensure_db_connection()
            await self._finalize_failure(
                chat_id, exc, response=final, accumulator=accumulator, run_ctx=run_ctx
            )
            raise
        finally:
            reset_run_viz_state()
            await run_plugin_end(run_ctx)
            await run_manager.complete(run.run_id)

    async def _persist_agent_messages(
        self,
        chat_id: uuid.UUID,
        response: Any,
        *,
        skip_tool_rows: bool = False,
    ) -> None:
        saved = 0
        call_names, call_arguments = _collect_call_context(getattr(response, "messages", None) or [])
        for message in getattr(response, "messages", None) or []:
            next_seq = await self._messages.next_sequence(chat_id)
            for row in maf_message_to_rows(
                str(chat_id),
                message,
                start_sequence=next_seq,
                call_names=call_names,
                call_arguments=call_arguments,
            ):
                if skip_tool_rows and row["message_type"] in _TOOL_ROW_TYPES:
                    continue
                await self._messages.insert(
                    chat_id=chat_id,
                    role=row["role"],
                    message_type=row["message_type"],
                    content=row.get("content"),
                    metadata=row.get("metadata"),
                    sequence=row["sequence"],
                )
                saved += 1
        text = getattr(response, "text", None)
        if text and saved == 0:
            await self._messages.insert(
                chat_id=chat_id,
                role="assistant",
                message_type="text",
                content=text,
            )
        await self._db.flush()


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def _normalize_tool_arguments(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return _json_safe(raw)
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return _json_safe(parsed)
        except json.JSONDecodeError:
            return {"raw": stripped}
    return {"raw": str(raw)}


def _tool_arguments_richness(arguments: dict[str, Any]) -> int:
    if not arguments:
        return 0
    try:
        return len(json.dumps(arguments, ensure_ascii=False, default=str))
    except TypeError:
        return len(str(arguments))


def _merge_tool_arguments(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> dict[str, Any]:
    left = existing or {}
    right = incoming or {}
    if _tool_arguments_richness(right) >= _tool_arguments_richness(left):
        return right
    return left


def _collect_call_context(messages: list[Any]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    names: dict[str, str] = {}
    arguments: dict[str, dict[str, Any]] = {}
    for message in messages:
        for content in getattr(message, "contents", None) or []:
            if getattr(content, "type", None) != "function_call":
                continue
            call_id = getattr(content, "call_id", None)
            tool_name = getattr(content, "name", None)
            if call_id is None:
                continue
            key = str(call_id)
            if tool_name:
                names[key] = str(tool_name)
            incoming = _normalize_tool_arguments(getattr(content, "arguments", {}))
            arguments[key] = _merge_tool_arguments(arguments.get(key), incoming)
    return names, arguments


def _collect_call_names(messages: list[Any]) -> dict[str, str]:
    names, _ = _collect_call_context(messages)
    return names


# Backward-compatible aliases for tests importing from run_service.
_proposal_updated_event = proposal_updated_event


def _emit_pending_artifact_events(
    chat_id: uuid.UUID,
    accumulator: StreamTurnAccumulator,
) -> list[dict[str, Any]]:
    return ArtifactStreamEmitter().drain_pending(chat_id, accumulator)


def _emit_pending_viz_events(
    chat_id: uuid.UUID,
    accumulator: StreamTurnAccumulator,
) -> list[dict[str, Any]]:
    return VizStreamEmitter().drain_pending(chat_id, accumulator)


def _emit_completed_slide_build_events(
    chat_id: uuid.UUID,
    accumulator: StreamTurnAccumulator,
) -> list[dict[str, Any]]:
    return SlideBuildStreamEmitter().drain_pending(chat_id, accumulator)


class StreamTurnAccumulator:
    """Tracks streamed assistant output for persistence when a run fails mid-turn."""

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []
        self._reasoning_buffer = ""
        self._text_buffer = ""
        self._emitted_calls: set[str] = set()
        self._emitted_results: set[str] = set()
        self._call_names: dict[str, str] = {}
        self._call_arguments: dict[str, dict[str, Any]] = {}
        self._viz_seq = 0

    def observe(self, update: Any) -> None:
        for content in getattr(update, "contents", None) or []:
            self._observe_content(content)

    def _append_reasoning(self, chunk: str) -> None:
        if not self._reasoning_buffer:
            self._reasoning_buffer = chunk
            return
        if chunk.startswith(self._reasoning_buffer):
            self._reasoning_buffer = chunk
            return
        if self._reasoning_buffer.startswith(chunk):
            return
        self._reasoning_buffer += chunk

    def _flush_reasoning(self) -> None:
        if not self._reasoning_buffer:
            return
        self._rows.append(
            {
                "role": "assistant",
                "message_type": "reasoning",
                "content": self._reasoning_buffer,
                "metadata": {},
            }
        )
        self._reasoning_buffer = ""

    def _flush_text(self) -> None:
        if not self._text_buffer:
            return
        self._rows.append(
            {
                "role": "assistant",
                "message_type": "text",
                "content": self._text_buffer,
                "metadata": {},
            }
        )
        self._text_buffer = ""

    def _append_text(self, chunk: str) -> None:
        if not self._text_buffer:
            self._text_buffer = chunk
            return
        if chunk.startswith(self._text_buffer):
            self._text_buffer = chunk
            return
        if self._text_buffer.startswith(chunk):
            return
        self._text_buffer += chunk

    def _observe_content(self, content: Any) -> None:
        content_type = getattr(content, "type", None)

        if content_type == "text_reasoning":
            text_chunk = getattr(content, "text", None)
            if text_chunk:
                self._append_reasoning(text_chunk)
            return

        if content_type in ("function_call", "function_result", "text"):
            self._flush_reasoning()

        if content_type == "function_call":
            call_id = str(getattr(content, "call_id", "") or "")
            tool_name = str(getattr(content, "name", "") or "").strip()
            if not call_id or not tool_name:
                return
            arguments = _normalize_tool_arguments(getattr(content, "arguments", {}))
            self._call_names[call_id] = tool_name
            merged = _merge_tool_arguments(self._call_arguments.get(call_id), arguments)
            self._call_arguments[call_id] = merged
            self._flush_text()
            if call_id in self._emitted_calls:
                for row in reversed(self._rows):
                    if row.get("message_type") != "tool_call":
                        continue
                    meta = row.get("metadata") or {}
                    if str(meta.get("call_id") or "") != call_id:
                        continue
                    meta["arguments"] = _merge_tool_arguments(meta.get("arguments"), arguments)
                    row["metadata"] = meta
                    break
                return
            self._emitted_calls.add(call_id)
            self._rows.append(
                {
                    "role": "assistant",
                    "message_type": "tool_call",
                    "content": None,
                    "metadata": {
                        "call_id": call_id,
                        "tool_name": tool_name,
                        "arguments": merged,
                    },
                }
            )
            return

        if content_type == "function_result":
            call_id = str(getattr(content, "call_id", "") or "")
            if not call_id or call_id in self._emitted_results:
                return
            self._emitted_results.add(call_id)
            result = _json_safe(getattr(content, "result", None))
            content_value = result if isinstance(result, str) else None
            self._rows.append(
                {
                    "role": "tool",
                    "message_type": "tool_result",
                    "content": content_value,
                    "metadata": {
                        "call_id": call_id,
                        "tool_name": self._call_names.get(call_id, ""),
                        "arguments": self._call_arguments.get(call_id, {}),
                        "result": result,
                    },
                }
            )
            return

        if content_type == "text":
            text = getattr(content, "text", None)
            if text:
                self._append_text(text)
            return

        if isinstance(content, str) and content:
            self._append_text(content)

    def record_viz(self, spec: VizSpec) -> None:
        self._flush_reasoning()
        self._flush_text()
        self._viz_seq += 1
        self._rows.append(
            {
                "role": "assistant",
                "message_type": "viz",
                "content": spec.title,
                "metadata": {"spec": viz_spec_payload(spec)},
            }
        )

    def record_artifact(self, spec: ArtifactSpec) -> None:
        self._flush_reasoning()
        self._flush_text()
        self._rows.append(
            {
                "role": "assistant",
                "message_type": "artifact",
                "content": spec.title,
                "metadata": {"spec": artifact_spec_payload(spec)},
            }
        )

    def _dedupe_text_vs_reasoning(self) -> None:
        """Drop assistant text that repeats streamed reasoning (model echo)."""
        text = (self._text_buffer or "").strip()
        if not text:
            return
        reasoning_parts = [
            str(row.get("content") or "").strip()
            for row in self._rows
            if row.get("message_type") == "reasoning"
        ]
        if not reasoning_parts:
            return
        combined = "\n".join(p for p in reasoning_parts if p).strip()
        if not combined:
            return
        if text == combined or combined in text or (len(text) > 80 and text in combined):
            self._text_buffer = ""

    def finalize(self) -> None:
        self._flush_reasoning()
        self._dedupe_text_vs_reasoning()
        self._flush_text()

    def enrich_tool_arguments_from_response(self, response: Any) -> None:
        """Merge final MAF response tool arguments into streamed rows (stream chunks are often empty)."""
        _, incoming_by_call = _collect_call_context(getattr(response, "messages", None) or [])
        for call_id, incoming in incoming_by_call.items():
            merged = _merge_tool_arguments(self._call_arguments.get(call_id), incoming)
            if not merged:
                continue
            self._call_arguments[call_id] = merged
            for row in self._rows:
                meta = row.get("metadata") or {}
                if str(meta.get("call_id") or "") != call_id:
                    continue
                if row.get("message_type") in ("tool_call", "tool_result", "mcp_call", "mcp_result"):
                    meta["arguments"] = merged
                    row["metadata"] = meta

    def has_content(self) -> bool:
        return bool(self._rows or self._reasoning_buffer or self._text_buffer)

    def has_tool_rows(self) -> bool:
        return any(row.get("message_type") in _TOOL_ROW_TYPES for row in self._rows)

    async def persist_tool_rows(self, repo: MessageRepository, chat_id: uuid.UUID) -> int:
        """Persist tool call/result rows captured during streaming (with full arguments)."""
        self.finalize()
        saved = 0
        for row in self._rows:
            if row.get("message_type") not in _TOOL_ROW_TYPES:
                continue
            await repo.insert(
                chat_id=chat_id,
                role=row["role"],
                message_type=row["message_type"],
                content=row.get("content"),
                metadata=row.get("metadata") or {},
            )
            saved += 1
        return saved

    async def persist(self, repo: MessageRepository, chat_id: uuid.UUID) -> int:
        self.finalize()
        saved = 0
        for row in self._rows:
            await repo.insert(chat_id=chat_id, **row)
            saved += 1
        return saved

    async def persist_cancelled(
        self,
        repo: MessageRepository,
        chat_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> int:
        """Write partial turn output; incomplete assistant text/reasoning marked cancelled."""
        self.finalize()
        run_meta = {"run_id": str(run_id)}
        saved = 0
        for row in self._rows:
            message_type = row["message_type"]
            meta = {**(row.get("metadata") or {}), **run_meta}
            if message_type in ("tool_call", "tool_result", "viz", "artifact"):
                await repo.insert(
                    chat_id=chat_id,
                    role=row["role"],
                    message_type=message_type,
                    content=row.get("content"),
                    metadata=meta,
                )
                saved += 1
                continue
            if message_type in ("reasoning", "text"):
                await repo.insert(
                    chat_id=chat_id,
                    role="assistant",
                    message_type="cancelled",
                    content=row.get("content"),
                    metadata={
                        **meta,
                        "partial": True,
                        "original_type": message_type,
                    },
                )
                saved += 1
        return saved


# Backward-compatible alias for tests and legacy imports.
_StreamTurnAccumulator = StreamTurnAccumulator


class _StreamSseEmitter:
    """Convert MAF stream updates into SSE events for the chat UI."""

    def __init__(
        self,
        chat_id: uuid.UUID,
        *,
        stream_emitters: list | None = None,
        accumulator: "_StreamTurnAccumulator | None" = None,
    ) -> None:
        self._chat_id = chat_id
        self._stream_emitters = stream_emitters or []
        self._accumulator = accumulator
        self._emitted_calls: set[str] = set()
        self._emitted_results: set[str] = set()
        self._call_names: dict[str, str] = {}
        self._call_arguments: dict[str, dict[str, Any]] = {}
        self._reasoning_open = False

    def _close_reasoning(self, chat_id: str) -> dict[str, Any] | None:
        if not self._reasoning_open:
            return None
        self._reasoning_open = False
        return {"event": "reasoning_done", "data": {"chat_id": chat_id}}

    def emit(self, update: Any) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        chat_id = str(self._chat_id)

        for content in getattr(update, "contents", None) or []:
            content_type = getattr(content, "type", None)

            if content_type == "text_reasoning":
                text = getattr(content, "text", None)
                if text:
                    self._reasoning_open = True
                    events.append(
                        {
                            "event": "reasoning",
                            "data": {"chat_id": chat_id, "text": text},
                        }
                    )
                continue

            if content_type in ("function_call", "function_result", "text"):
                done = self._close_reasoning(chat_id)
                if done:
                    events.append(done)

            if content_type == "function_call":
                call_id = str(getattr(content, "call_id", "") or "")
                tool_name = str(getattr(content, "name", "") or "").strip()
                if not call_id or not tool_name:
                    continue
                arguments = _normalize_tool_arguments(getattr(content, "arguments", {}))
                self._call_names[call_id] = tool_name
                merged = _merge_tool_arguments(self._call_arguments.get(call_id), arguments)
                self._call_arguments[call_id] = merged
                self._emitted_calls.add(call_id)
                events.append(
                    {
                        "event": "tool_call",
                        "data": {
                            "chat_id": chat_id,
                            "call_id": call_id,
                            "tool_name": tool_name,
                            "arguments": merged,
                        },
                    }
                )
                continue

            if content_type == "function_result":
                call_id = str(getattr(content, "call_id", "") or "")
                if not call_id or call_id in self._emitted_results:
                    continue
                self._emitted_results.add(call_id)
                tool_name = self._call_names.get(call_id, "")
                result_data: dict[str, Any] = {
                    "chat_id": chat_id,
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "arguments": self._call_arguments.get(call_id, {}),
                    "result": _json_safe(getattr(content, "result", None)),
                }
                exception = getattr(content, "exception", None)
                if exception:
                    result_data["error"] = str(exception)
                events.append(
                    {
                        "event": "tool_result",
                        "data": result_data,
                    }
                )
                if self._stream_emitters and self._accumulator is not None:
                    events.extend(
                        tool_result_stream_events(
                            self._stream_emitters,
                            self._chat_id,
                            tool_name,
                            self._accumulator,
                        )
                    )
                continue

            if content_type == "text":
                text = getattr(content, "text", None)
                if text:
                    events.append(
                        {
                            "event": "text",
                            "data": {"chat_id": chat_id, "text": text},
                        }
                    )
            elif isinstance(content, str) and content:
                done = self._close_reasoning(chat_id)
                if done:
                    events.append(done)
                events.append(
                    {
                        "event": "text",
                        "data": {"chat_id": chat_id, "text": content},
                    }
                )

        return events

    def flush(self) -> list[dict[str, Any]]:
        done = self._close_reasoning(str(self._chat_id))
        return [done] if done else []


async def list_chat_messages(db: AsyncSession, chat_id: uuid.UUID) -> list[dict[str, Any]]:
    repo = MessageRepository(db)
    rows = await repo.list_by_chat(chat_id)
    return [
        {
            "id": str(r.id),
            "chat_id": str(r.chat_id),
            "role": r.role,
            "message_type": r.message_type,
            "content": r.content,
            "metadata": r.message_metadata,
            "parent_id": str(r.parent_id) if r.parent_id else None,
            "sequence": r.sequence,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

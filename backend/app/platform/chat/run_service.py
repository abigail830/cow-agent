from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from agent_framework import Content, Message, MiddlewareTermination
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentModel, Chat, ChatMessage
from app.db.repositories.chat_messages import ChatMessageRepository
from app.db.repositories.chat_runs import ChatRunRepository
from app.db.repositories.chat_ui_annotations import ChatUiAnnotationRepository
from app.platform.chat.timeline_projection import (
    build_turn_message_outs,
    display_sequence,
    merge_timeline_to_message_outs,
)
from app.platform.memory.long_term import try_handle_memory_command
from app.platform.memory.context_budget import estimate_context_usage
from app.platform.memory.memory_config import (
    MemoryConfig,
    apply_model_compaction_defaults,
    parse_memory_config,
)
from app.platform.agent.agent_factory import AgentFactory
from app.platform.mcp.mcp_connect import disconnect_bundle, iter_mcp_connect_keepalive
from app.platform.mcp.mcp_pool import McpPoolKey, get_mcp_connection_pool
from app.platform.session.session_store import SessionStore
from app.platform.session.user_message_input import link_attachments_metadata
from app.platform.attachments.materialize import (
    build_user_message_with_attachments,
    prior_full_attachment_ids_in_context,
)
from app.platform.memory.message_validate import message_from_body
from app.platform.chat.title_service import maybe_schedule_chat_title_generation
from app.platform.chat.user_message_commit import build_user_maf_message, persist_user_maf_message
from app.platform.attachments.service import AttachmentService
from app.platform.llm.chat_model import resolve_chat_model
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
    drain_after_finalize,
    drain_remaining_stream_events,
    drain_stream_events,
    tool_result_stream_events,
)
from app.agent_specific.viz.stream_emitter import VizStreamEmitter, viz_spec_payload
from app.shared.artifacts.stream_emitter import ArtifactStreamEmitter, artifact_spec_payload
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
        self._messages = ChatMessageRepository(db)
        self._annotations = ChatUiAnnotationRepository(db)
        self._runs = ChatRunRepository(db)
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

    async def _resolve_attachments(
        self,
        chat: Chat,
        attachment_ids: list[uuid.UUID],
    ) -> list:
        if not attachment_ids:
            return []
        service = AttachmentService(self._db)
        return await service.resolve_for_message(chat.id, attachment_ids)

    async def _prepare_user_turn_metadata(
        self,
        chat: Chat,
        attachments: list,
    ) -> dict[str, Any]:
        del chat
        return link_attachments_metadata({}, attachments)

    async def _prior_already_full_attachment_ids(
        self,
        chat_id: uuid.UUID,
        *,
        model_id: str | None = None,
        model_provider: str | None = None,
    ) -> set[str]:
        prior_rows = await self._messages.list_by_chat(chat_id)
        if not prior_rows:
            return set()
        return prior_full_attachment_ids_in_context(
            [message_from_body(row.body) for row in prior_rows],
            chat_id=chat_id,
            model_id=model_id,
            provider=model_provider,
        )

    async def _build_run_input(
        self,
        chat: Chat,
        content: str,
        attachments: list,
        *,
        model_id: str | None = None,
        model_provider: str | None = None,
        already_full_inlined: set[str] | None = None,
    ):
        if not attachments:
            return content.strip() or content
        return build_user_message_with_attachments(
            content,
            attachments,
            chat_id=chat.id,
            model_id=model_id,
            provider=model_provider,
            already_full_inlined=already_full_inlined,
        )

    async def _resolve_run_model(self, chat: Chat) -> tuple[str, str]:
        model_entry = await resolve_chat_model(self._db, chat)
        return model_entry.id, model_entry.provider

    async def _mcp_pool_key(self, chat: Chat) -> McpPoolKey:
        return McpPoolKey(
            user_id=chat.user_id,
            chat_id=chat.id,
            agent_id=chat.agent_id,
            config_fingerprint=await self._factory._mcp.config_fingerprint(
                chat.agent_id,
                user_id=chat.user_id,
            ),
        )

    async def warmup_chat(self, chat: Chat) -> None:
        """Pre-connect MCP tools for *chat* so the first run can pool-hit."""
        await self._sessions.get_or_create(chat.id)
        agent_row = await self._factory.get_agent_row(chat.agent_id)
        pool = get_mcp_connection_pool()
        pool_key = await self._mcp_pool_key(chat)

        async def factory() -> list[Any]:
            return await self._factory._mcp.resolve_for_agent(
                chat.agent_id,
                agent_config=agent_row.config,
                user_id=chat.user_id,
            )

        handle = await pool.acquire(pool_key, factory)
        await pool.release(handle)

    async def _build_pooled_bundle(
        self,
        chat: Chat,
        *,
        model_id: str | None,
        turn_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        stop_event: asyncio.Event | None = None,
        session_store: SessionStore | None = None,
    ) -> Any:
        agent_row = await self._factory.get_agent_row(chat.agent_id)
        pool = get_mcp_connection_pool()
        pool_key = await self._mcp_pool_key(chat)

        async def factory() -> list[Any]:
            return await self._factory._mcp.resolve_for_agent(
                chat.agent_id,
                agent_config=agent_row.config,
                user_id=chat.user_id,
            )

        handle = await pool.acquire(pool_key, factory)
        try:
            return await self._factory.build(
                chat.agent_id,
                chat_id=chat.id,
                user_id=chat.user_id,
                model_id=model_id,
                turn_id=turn_id,
                run_id=run_id,
                stop_event=stop_event,
                session_store=session_store,
                mcp_tools=handle.tools,
                mcp_pool_handle=handle,
            )
        except Exception:
            await pool.release(handle)
            await pool.invalidate(pool_key)
            raise

    async def _release_bundle(self, bundle: Any, *, invalidate_on_error: bool = False) -> None:
        handle = getattr(bundle, "mcp_pool_handle", None)
        if handle is None:
            await disconnect_bundle(bundle)
            return
        pool = get_mcp_connection_pool()
        if invalidate_on_error:
            await pool.invalidate(handle.key)
            return
        await pool.release(handle)

    async def _insert_assistant_text(
        self,
        chat_id: uuid.UUID,
        *,
        turn_id: uuid.UUID,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        props: dict[str, Any] = {"platform": dict(metadata or {})}
        body = Message(
            role="assistant",
            contents=[Content.from_text(text)],
            additional_properties=props,
        ).to_dict()
        return await self._messages.insert(
            chat_id=chat_id,
            turn_id=turn_id,
            body=body,
        )

    async def _commit_user_turn(
        self,
        chat: Chat,
        content: str,
        *,
        turn_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        attachments: list | None = None,
        attachment_ids: list[uuid.UUID] | None = None,
        metadata: dict[str, Any] | None = None,
        commit: bool = True,
        already_full_inlined: set[str] | None = None,
    ) -> ChatMessage:
        """Persist the user MAF message immediately so it survives agent failures."""
        resolved = (
            attachments
            if attachments is not None
            else await self._resolve_attachments(chat, attachment_ids or [])
        )
        if metadata is None:
            metadata = await self._prepare_user_turn_metadata(chat, resolved)
        model_id, model_provider = await self._resolve_run_model(chat)
        turn = turn_id or uuid.uuid4()
        if already_full_inlined is None:
            already_full_inlined = await self._prior_already_full_attachment_ids(
                chat.id,
                model_id=model_id,
                model_provider=model_provider,
            )
        message = build_user_maf_message(
            chat.id,
            content,
            resolved,
            model_id=model_id,
            model_provider=model_provider,
            metadata=metadata,
            already_full_inlined=already_full_inlined,
        )
        row = await persist_user_maf_message(
            self._db,
            chat_id=chat.id,
            turn_id=turn,
            message=message,
            run_id=run_id,
            attachment_ids=[att.id for att in resolved] if resolved else None,
        )
        await self._maybe_set_chat_title(chat, content, resolved)
        if commit:
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
        *,
        turn_id: uuid.UUID | None = None,
    ) -> None:
        """Persist partial assistant output and mark the run cancelled."""
        try:
            if turn_id is not None:
                if accumulator.has_content():
                    await accumulator.persist_partial_assistant(
                        self._messages,
                        chat_id,
                        turn_id=turn_id,
                        run_id=run_id,
                        cancelled=True,
                    )
                turn_messages = await self._messages.list_by_turn(chat_id, turn_id)
                await accumulator.persist_ui_timeline(self._messages, turn_messages)
                await accumulator.persist_ui_annotations(self._annotations, chat_id, turn_id)
            await self._runs.cancel(run_id)
            await self._db.commit()
        except Exception:
            logger.exception("Failed to persist cancelled turn for chat %s", chat_id)
            await self._db.rollback()

    async def _memory_config_for_chat(self, chat: Chat) -> MemoryConfig:
        agent = await self._db.get(AgentModel, chat.agent_id)
        base = parse_memory_config(agent.config if agent else {})
        model_entry = await resolve_chat_model(self._db, chat)
        return apply_model_compaction_defaults(base, model_entry)

    async def snapshot_context_usage(self, chat: Chat, *, memory_config: MemoryConfig | None = None) -> dict[str, Any] | None:
        resolved = memory_config or await self._memory_config_for_chat(chat)
        model_entry = await resolve_chat_model(self._db, chat)
        snapshot = await estimate_context_usage(
            db=self._db,
            chat_id=chat.id,
            memory_config=resolved,
            model_id=model_entry.id,
            model_provider=model_entry.provider,
        )
        return snapshot.to_dict() if snapshot is not None else None

    async def get_cached_context_usage(self, chat_id: uuid.UUID) -> dict[str, Any] | None:
        payload = await self._sessions.get_payload(chat_id)
        cached = payload.get("context_usage")
        return cached if isinstance(cached, dict) else None

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

    async def _prepare_run_plugins(
        self,
        chat: Chat,
        *,
        turn_attachment_ids: frozenset[str] | None = None,
    ) -> RunContext:
        ctx = await self._build_run_context(chat)
        if turn_attachment_ids is not None:
            ctx.turn_attachment_ids = turn_attachment_ids
        await run_plugin_start(ctx)
        init_run_viz_state()
        return ctx

    async def _finalize_success(
        self,
        chat_id: uuid.UUID,
        session: Any,
        response: Any,
        *,
        memory_config: MemoryConfig | None = None,
        run_ctx: RunContext | None = None,
        accumulator: "_StreamTurnAccumulator | None" = None,
        user_message: ChatMessage | None = None,
        turn_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        if accumulator is not None and turn_id is not None:
            accumulator.enrich_tool_arguments_from_response(response)
            turn_messages = await self._messages.list_by_turn(chat_id, turn_id)
            await accumulator.persist_ui_timeline(self._messages, turn_messages)
            await accumulator.persist_ui_annotations(self._annotations, chat_id, turn_id)
        if run_id is not None:
            await self._runs.complete(run_id)
        payload_extensions: dict[str, Any] = {}
        if run_ctx is not None:
            payload_extensions = await run_plugin_finalize_success(run_ctx, accumulator=accumulator)
        if run_ctx is not None and run_ctx.context_usage is not None:
            payload_extensions["context_usage"] = run_ctx.context_usage
        await self._sessions.finalize_run(
            chat_id,
            session,
            payload_extensions=payload_extensions or None,
        )
        await self._db.commit()
        if user_message is not None:
            await maybe_schedule_chat_title_generation(
                self._db,
                chat_id=chat_id,
                user_message_id=user_message.id,
            )
        if turn_id is None or user_message is None:
            return []
        turn_messages = await self._messages.list_by_turn(chat_id, turn_id)
        turn_annotations = [
            row
            for row in await self._annotations.list_by_chat(chat_id)
            if row.turn_id == turn_id
        ]
        assistant_messages = [row for row in turn_messages if row.id != user_message.id]
        return build_turn_message_outs(
            chat_id,
            user_message,
            assistant_messages,
            turn_annotations,
        )

    async def _finalize_failure(
        self,
        chat_id: uuid.UUID,
        exc: Exception,
        *,
        response: Any | None = None,
        run_ctx: RunContext | None = None,
        accumulator: "_StreamTurnAccumulator | None" = None,
        memory_config: MemoryConfig | None = None,
        turn_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> None:
        """Best-effort persist of partial assistant output plus run failure status."""
        try:
            if accumulator is not None and turn_id is not None:
                if accumulator.has_content():
                    await accumulator.persist_partial_assistant(
                        self._messages,
                        chat_id,
                        turn_id=turn_id,
                        run_id=run_id,
                        cancelled=False,
                    )
                turn_messages = await self._messages.list_by_turn(chat_id, turn_id)
                await accumulator.persist_ui_timeline(self._messages, turn_messages)
                await accumulator.persist_ui_annotations(self._annotations, chat_id, turn_id)
            if run_ctx is not None:
                extensions = await run_plugin_finalize_failure(run_ctx, accumulator=accumulator)
                for key, value in extensions.items():
                    await self._sessions.merge_extension(chat_id, key, value)
            if run_id is not None:
                await self._runs.fail(run_id, error=user_facing_stream_error(exc)[:4000])
            await self._db.commit()
        except Exception:
            logger.exception("Failed to persist partial turn for chat %s", chat_id)
            await self._db.rollback()

    async def _persist_pending_artifacts(
        self,
        chat_id: uuid.UUID,
        *,
        turn_id: uuid.UUID,
    ) -> None:
        specs: list[ArtifactSpec] = []
        proposal_ctx = get_run_proposal_state()
        if proposal_ctx is not None:
            specs.extend(proposal_ctx.drain_pending_artifacts())
        artifact_ctx = get_run_artifact_state()
        if artifact_ctx is not None:
            specs.extend(artifact_ctx.drain_pending_artifacts())
        rows: list[dict[str, Any]] = []
        for spec in specs:
            rows.append(
                {
                    "turn_id": turn_id,
                    "kind": "artifact",
                    "ref": spec.artifact_id,
                    "display": {"title": spec.title, "spec": artifact_spec_payload(spec)},
                }
            )
        if rows:
            await self._annotations.insert_many(chat_id, rows)

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
        model_id, model_provider = await self._resolve_run_model(chat)
        attachments = await self._resolve_attachments(chat, attachment_ids or [])
        if not content.strip() and not attachments:
            raise ValueError("Message content or attachments required")
        run_ctx = await self._prepare_run_plugins(
            chat,
            turn_attachment_ids=frozenset(str(att.id) for att in attachments),
        )
        turn_id = uuid.uuid4()
        run_id = uuid.uuid4()
        already_full = await self._prior_already_full_attachment_ids(
            chat.id,
            model_id=model_id,
            model_provider=model_provider,
        )
        user_message = await self._commit_user_turn(
            chat,
            content,
            turn_id=turn_id,
            run_id=run_id,
            attachments=attachments,
            attachment_ids=attachment_ids,
            commit=False,
            already_full_inlined=already_full,
        )
        await self._runs.create(
            chat_id=chat_id,
            run_id=run_id,
            user_message_id=user_message.id,
            model_id=model_id,
        )
        await self._db.commit()
        memory_result = await try_handle_memory_command(
            self._db,
            user_id=chat.user_id,
            agent_id=chat.agent_id,
            content=content,
        )
        if memory_result and memory_result.handled:
            if memory_result.is_pure_command:
                await self._insert_assistant_text(
                    chat_id,
                    turn_id=turn_id,
                    text=memory_result.confirmation,
                    metadata={"source": "memory_command"},
                )
                await self._runs.complete(run_id)
            await self._db.commit()
            if memory_result.is_pure_command:
                reset_run_viz_state()
                await run_plugin_end(run_ctx)
                return memory_result.confirmation
        bundle = await self._build_pooled_bundle(
            chat,
            model_id=model_id,
            turn_id=turn_id,
            run_id=run_id,
            session_store=self._sessions,
        )
        try:
            async with bundle as agent:
                result = await agent.run(None, session=session)
            await self._persist_pending_artifacts(chat_id, turn_id=turn_id)
            await self._finalize_success(
                chat_id,
                session,
                result,
                memory_config=memory_config,
                run_ctx=run_ctx,
                user_message=user_message,
                turn_id=turn_id,
                run_id=run_id,
            )
            return result.text or ""
        except Exception as exc:
            await self._finalize_failure(
                chat_id,
                exc,
                run_ctx=run_ctx,
                memory_config=memory_config,
                turn_id=turn_id,
                run_id=run_id,
            )
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
        model_id, model_provider = await self._resolve_run_model(chat)
        attachments = await self._resolve_attachments(chat, attachment_ids or [])
        if not content.strip() and not attachments:
            raise ValueError("Message content or attachments required")
        run_ctx = await self._prepare_run_plugins(
            chat,
            turn_attachment_ids=frozenset(str(att.id) for att in attachments),
        )
        turn_id = uuid.uuid4()
        already_full = await self._prior_already_full_attachment_ids(
            chat.id,
            model_id=model_id,
            model_provider=model_provider,
        )
        user_message = await self._commit_user_turn(
            chat,
            content,
            turn_id=turn_id,
            attachments=attachments,
            attachment_ids=attachment_ids,
            commit=False,
            already_full_inlined=already_full,
        )
        memory_result = await try_handle_memory_command(
            self._db,
            user_id=chat.user_id,
            agent_id=chat.agent_id,
            content=content,
        )
        if memory_result and memory_result.handled:
            if memory_result.is_pure_command:
                await self._insert_assistant_text(
                    chat_id,
                    turn_id=turn_id,
                    text=memory_result.confirmation,
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
                turn_messages = await self._list_turn_messages_since(chat_id, user_message.sequence)
                yield {
                    "event": "done",
                    "data": {
                        "text": memory_result.confirmation,
                        "turn_start_sequence": user_message.sequence,
                        "turn_start_display_sequence": display_sequence(user_message.sequence),
                        "messages": turn_messages,
                    },
                }
                return

        run_manager = get_run_manager()
        run = await run_manager.start_run(chat_id, user_message.id)
        run_ctx.run_id = run.run_id
        await self._runs.create(
            chat_id=chat_id,
            run_id=run.run_id,
            user_message_id=user_message.id,
            model_id=model_id,
        )
        user_message.run_id = run.run_id
        await self._db.commit()
        stream_emitters = collect_stream_emitters(run_ctx.agent_slug)
        accumulator = _StreamTurnAccumulator(turn_id=turn_id)

        emitter = _StreamSseEmitter(
            chat_id,
            stream_emitters=stream_emitters,
            accumulator=accumulator,
        )

        async def finalize_cancel_once() -> None:
            await self._finalize_cancel(
                chat_id,
                run.run_id,
                accumulator,
                turn_id=turn_id,
            )

        await run_manager.register_finalize(run.run_id, finalize_cancel_once)
        yield {
            "event": "run_started",
            "data": {
                "run_id": str(run.run_id),
                "chat_id": str(chat_id),
                "user_message_id": str(user_message.id),
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
            bundle = await self._build_pooled_bundle(
                chat,
                model_id=model_id,
                turn_id=turn_id,
                run_id=run.run_id,
                stop_event=run.stop_event,
                session_store=self._sessions,
            )
            async for keepalive in iter_mcp_connect_keepalive(bundle):
                yield keepalive
            agent = bundle.agent
            try:
                stream = agent.run(None, session=session, stream=True)
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
                await self._release_bundle(bundle)

            context_usage = await self.snapshot_context_usage(chat, memory_config=memory_config)
            if context_usage is not None:
                run_ctx.context_usage = context_usage

            # Unlock client UI before DB/session persistence (can take seconds on tool-heavy turns).
            stream_idle_data: dict[str, Any] = {
                "chat_id": str(chat_id),
                "run_id": str(run.run_id),
            }
            if context_usage is not None:
                stream_idle_data["context_usage"] = context_usage
            yield {
                "event": "stream_idle",
                "data": stream_idle_data,
            }

            await self._ensure_db_connection()
            turn_messages = await self._finalize_success(
                chat_id,
                session,
                final,
                memory_config=memory_config,
                run_ctx=run_ctx,
                accumulator=accumulator,
                user_message=user_message,
                turn_id=turn_id,
                run_id=run.run_id,
            )
            for event in drain_after_finalize(stream_emitters, chat_id, accumulator):
                yield event
            done_data: dict[str, Any] = {
                "text": final.text or "",
                "turn_start_sequence": user_message.sequence,
                "turn_start_display_sequence": display_sequence(user_message.sequence),
                "messages": turn_messages,
            }
            if context_usage is not None:
                done_data["context_usage"] = context_usage
            yield {
                "event": "done",
                "data": done_data,
            }
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
                chat_id,
                exc,
                response=final,
                accumulator=accumulator,
                run_ctx=run_ctx,
                memory_config=memory_config,
                turn_id=turn_id,
                run_id=run.run_id,
            )
            raise
        finally:
            reset_run_viz_state()
            await run_plugin_end(run_ctx)
            await run_manager.complete(run.run_id)

    async def _list_turn_messages_since(
        self, chat_id: uuid.UUID, turn_start_sequence: int
    ) -> list[dict[str, Any]]:
        messages = await self._messages.list_by_chat_since(chat_id, turn_start_sequence)
        annotations = await self._annotations.list_by_chat_since(chat_id, turn_start_sequence)
        return merge_timeline_to_message_outs(
            chat_id=chat_id,
            messages=messages,
            annotations=annotations,
        )


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


class StreamTurnAccumulator:
    """Tracks streamed assistant output for SSE and ui_annotation persistence."""

    def __init__(self, *, turn_id: uuid.UUID | None = None) -> None:
        self._turn_id = turn_id
        self._rows: list[dict[str, Any]] = []
        self._ui_annotations: list[dict[str, Any]] = []
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
        if self._turn_id is not None:
            self._ui_annotations.append(
                {
                    "turn_id": self._turn_id,
                    "kind": "viz",
                    "ref": spec.source_call_id or spec.title,
                    "display": {"title": spec.title, "spec": viz_spec_payload(spec)},
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
        if self._turn_id is not None:
            self._ui_annotations.append(
                {
                    "turn_id": self._turn_id,
                    "kind": "artifact",
                    "ref": spec.artifact_id,
                    "display": {"title": spec.title, "spec": artifact_spec_payload(spec)},
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

    def build_ui_timeline(self) -> list[dict[str, Any]]:
        """Ordered UI rows (text ↔ artifact interleave) captured during streaming."""
        items: list[dict[str, Any]] = []
        for row in self._rows:
            message_type = row.get("message_type")
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            if message_type == "text":
                items.append({"kind": "text", "content": row.get("content") or "", "metadata": metadata})
            elif message_type == "reasoning":
                items.append({"kind": "reasoning", "content": row.get("content") or "", "metadata": metadata})
            elif message_type in ("tool_call", "mcp_call"):
                items.append({"kind": "tool_call", "metadata": metadata})
            elif message_type == "tool_result":
                items.append(
                    {
                        "kind": "tool_result",
                        "content": row.get("content"),
                        "metadata": metadata,
                    }
                )
            elif message_type == "artifact":
                items.append({"kind": "artifact", "metadata": metadata})
            elif message_type == "viz":
                items.append(
                    {
                        "kind": "viz",
                        "content": row.get("content"),
                        "metadata": metadata,
                    }
                )
        return items

    async def persist_ui_timeline(
        self,
        repo: ChatMessageRepository,
        turn_messages: list[Any],
    ) -> bool:
        """Persist interleaved stream order on the anchor assistant message."""
        self.finalize()
        timeline = self.build_ui_timeline()
        if not timeline:
            return False
        if not any(item.get("kind") in {"artifact", "viz"} for item in timeline):
            return False
        anchor = next((message for message in turn_messages if message.role == "assistant"), None)
        if anchor is None:
            return False

        body = dict(anchor.body) if isinstance(anchor.body, dict) else {}
        props = dict(body.get("additional_properties") or {})
        platform = dict(props.get("platform") or {}) if isinstance(props.get("platform"), dict) else {}
        platform["ui_timeline"] = timeline
        props["platform"] = platform
        body["additional_properties"] = props
        await repo.update_body(anchor.id, body)
        return True

    async def persist_ui_annotations(
        self,
        repo: ChatUiAnnotationRepository,
        chat_id: uuid.UUID,
        turn_id: uuid.UUID,
    ) -> int:
        if not self._ui_annotations:
            return 0
        rows = [{**row, "turn_id": turn_id} for row in self._ui_annotations]
        await repo.insert_many(chat_id, rows)
        self._ui_annotations.clear()
        return len(rows)

    async def persist_partial_assistant(
        self,
        repo: ChatMessageRepository,
        chat_id: uuid.UUID,
        *,
        turn_id: uuid.UUID,
        run_id: uuid.UUID | None,
        cancelled: bool,
    ) -> None:
        """Best-effort partial assistant MAF message for cancel/failure paths."""
        self.finalize()
        if not self._rows:
            return
        from app.platform.memory.maf_mapping import to_maf_messages

        # Partial persist is UI-only: never write tool_call/tool rows to LLM history.
        _PARTIAL_ROW_TYPES = frozenset({"reasoning", "text"})
        platform_rows = [
            row
            for row in self._rows
            if row.get("message_type") in _PARTIAL_ROW_TYPES
        ]
        if cancelled:
            platform_rows = [
                {
                    **row,
                    "message_type": "cancelled",
                    "metadata": {
                        **(row.get("metadata") or {}),
                        "partial": True,
                        "original_type": row.get("message_type"),
                    },
                }
                for row in platform_rows
            ]
        messages = to_maf_messages(platform_rows)
        if not messages:
            return
        combined = Message(
            role="assistant",
            contents=[content for message in messages for content in (message.contents or [])],
            additional_properties={
                "platform": {
                    "partial": True,
                    "cancelled": cancelled,
                    "run_id": str(run_id) if run_id else None,
                }
            },
        )
        await repo.insert(
            chat_id=chat_id,
            turn_id=turn_id,
            body=combined.to_dict(),
            run_id=run_id,
        )


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
    """Legacy flat MessageOut list (expanded from MAF rows). Prefer GET /timeline."""
    messages = await ChatMessageRepository(db).list_by_chat(chat_id)
    annotations = await ChatUiAnnotationRepository(db).list_by_chat(chat_id)
    return merge_timeline_to_message_outs(
        chat_id=chat_id,
        messages=messages,
        annotations=annotations,
        include_run_markers=False,
    )


async def list_chat_timeline(db: AsyncSession, chat_id: uuid.UUID) -> dict[str, Any]:
    from app.platform.audio_capture.webhook import reconcile_audio_transcript_artifacts_for_chat
    from app.platform.chat.timeline_projection import build_timeline_response

    if await reconcile_audio_transcript_artifacts_for_chat(db, chat_id):
        await db.commit()

    messages = await ChatMessageRepository(db).list_by_chat(chat_id)
    annotations = await ChatUiAnnotationRepository(db).list_by_chat(chat_id)
    runs = await ChatRunRepository(db).list_by_chat(chat_id)
    return build_timeline_response(
        chat_id=chat_id,
        messages=messages,
        annotations=annotations,
        runs=runs,
    )

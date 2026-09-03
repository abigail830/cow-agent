"""Handle external events → new chat session + initial user message."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentModel, Chat
from app.db.repositories.messages import MessageRepository
from app.platform.platform_sync import agent_id_for_slug
from app.services.chat_run import ChatRunService
from app.yl_worker2.triggers.schemas import YlWorker2TriggerPayload, YlWorker2TriggerResponse

AGENT_SLUG = "yl-worker2"


def render_trigger_message(payload: YlWorker2TriggerPayload) -> str:
    """Build the first user turn from webhook payload."""
    if payload.event_type == "base_inbound_delay":
        avail = payload.detail.get("from_available_after", "未知")
        return (
            f"【外系统事件】基地仓入库延期：产品 {payload.product_code}，"
            f"基地 {payload.site_code or '未知'}，快照日 {payload.adjust_date}，"
            f"可发量降至 {avail} 件。请检查待确认正向/横向草案是否仍可行，"
            f"给出调整建议并说明依据（先 list_pending_allocation_orders）。"
        )
    if payload.event_type == "large_order_added":
        delta = payload.detail.get("order_delta", payload.detail.get("unship_delta", "未知"))
        return (
            f"【外系统事件】大客户追加订单：产品 {payload.product_code}，"
            f"销售仓 {payload.site_code or '未知'}，快照日 {payload.adjust_date}，"
            f"未发订单增加约 {delta} 件。请重算目标备货率与补货需求，"
            f"必要时追加或调整草案。"
        )
    if payload.event_type == "inventory_snapshot_changed":
        return (
            f"【外系统事件】库存快照变更：产品 {payload.product_code}，"
            f"仓 {payload.site_code or '全国'}，日期 {payload.adjust_date}。"
            f"详情：{payload.detail}。请评估对既有补调方案的影响。"
        )
    return (
        f"【外系统事件】{payload.event_type}：产品 {payload.product_code}，"
        f"快照日 {payload.adjust_date}，详情 {payload.detail}。请按本体 Tool 流程分析并给出建议。"
    )


async def _persist_trigger_user_message(
    db: AsyncSession,
    chat_id: uuid.UUID,
    content: str,
) -> None:
    repo = MessageRepository(db)
    await repo.insert(
        chat_id=chat_id,
        role="user",
        message_type="text",
        content=content,
        metadata={"source": "yl_worker2_trigger"},
    )


async def handle_yl_worker2_trigger(
    db: AsyncSession,
    payload: YlWorker2TriggerPayload,
    *,
    user_id: uuid.UUID,
    auto_run: bool = True,
) -> YlWorker2TriggerResponse:
    agent_id = agent_id_for_slug(AGENT_SLUG)
    agent = await db.get(AgentModel, agent_id)
    if agent is None:
        raise ValueError(f"Agent {AGENT_SLUG} not synced; run platform_sync first")

    initial_message = render_trigger_message(payload)
    title = f"事件补调 · {payload.event_type} · {payload.product_code}"
    chat = Chat(user_id=user_id, agent_id=agent_id, title=title)
    db.add(chat)
    await db.flush()

    if auto_run:
        service = ChatRunService(db)
        await service.run_message(chat.id, initial_message)
        status = "session_created_and_run_completed"
    else:
        await _persist_trigger_user_message(db, chat.id, initial_message)
        status = "session_created"

    await db.commit()
    return YlWorker2TriggerResponse(
        chat_id=str(chat.id),
        agent_slug=AGENT_SLUG,
        initial_message=initial_message,
        status=status,
    )

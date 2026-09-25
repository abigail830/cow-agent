import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentModel, Chat, ChatAttachment


class AttachmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, attachment_id: uuid.UUID) -> ChatAttachment | None:
        return await self._session.get(ChatAttachment, attachment_id)

    async def list_for_chat(self, chat_id: uuid.UUID) -> list[ChatAttachment]:
        result = await self._session.execute(
            select(ChatAttachment)
            .where(ChatAttachment.chat_id == chat_id)
            .order_by(ChatAttachment.created_at.desc())
        )
        return list(result.scalars().all())

    def _apply_user_document_filters(
        self,
        stmt,
        *,
        q: str | None = None,
        parse_status: str | None = None,
        mime_type: str | None = None,
        agent_id: uuid.UUID | None = None,
    ):
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(ChatAttachment.filename.ilike(pattern))
        if parse_status:
            stmt = stmt.where(ChatAttachment.parse_status == parse_status.strip())
        if mime_type:
            stmt = stmt.where(ChatAttachment.mime_type.ilike(f"{mime_type.strip()}%"))
        if agent_id is not None:
            stmt = stmt.where(Chat.agent_id == agent_id)
        return stmt

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        q: str | None = None,
        parse_status: str | None = None,
        mime_type: str | None = None,
        agent_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[ChatAttachment, Chat, AgentModel]], int]:
        count_stmt = (
            select(func.count(ChatAttachment.id))
            .select_from(ChatAttachment)
            .join(Chat, ChatAttachment.chat_id == Chat.id)
            .where(Chat.user_id == user_id)
        )
        count_stmt = self._apply_user_document_filters(
            count_stmt,
            q=q,
            parse_status=parse_status,
            mime_type=mime_type,
            agent_id=agent_id,
        )
        count_result = await self._session.execute(count_stmt)
        total = int(count_result.scalar_one())

        list_stmt = (
            select(ChatAttachment, Chat, AgentModel)
            .join(Chat, ChatAttachment.chat_id == Chat.id)
            .join(AgentModel, Chat.agent_id == AgentModel.id)
            .where(Chat.user_id == user_id)
        )
        list_stmt = self._apply_user_document_filters(
            list_stmt,
            q=q,
            parse_status=parse_status,
            mime_type=mime_type,
            agent_id=agent_id,
        )
        list_stmt = list_stmt.order_by(ChatAttachment.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(list_stmt)
        return list(result.all()), total

    async def list_by_ids(self, chat_id: uuid.UUID, attachment_ids: list[uuid.UUID]) -> list[ChatAttachment]:
        if not attachment_ids:
            return []
        result = await self._session.execute(
            select(ChatAttachment).where(
                ChatAttachment.chat_id == chat_id,
                ChatAttachment.id.in_(attachment_ids),
            )
        )
        rows = list(result.scalars().all())
        order = {aid: idx for idx, aid in enumerate(attachment_ids)}
        rows.sort(key=lambda row: order.get(row.id, len(order)))
        return rows

    async def find_by_content_hash(
        self,
        chat_id: uuid.UUID,
        content_hash: str,
        *,
        provider: str | None = None,
    ) -> ChatAttachment | None:
        query = select(ChatAttachment).where(
            ChatAttachment.chat_id == chat_id,
            ChatAttachment.content_hash == content_hash,
        )
        if provider is not None:
            query = query.where(ChatAttachment.provider == provider)
        result = await self._session.execute(query.limit(1))
        return result.scalar_one_or_none()

    async def update_gist(self, attachment_id: uuid.UUID, gist: str) -> ChatAttachment | None:
        row = await self.get(attachment_id)
        if row is None:
            return None
        row.gist = gist.strip() or None
        await self._session.flush()
        return row

    async def update_provider_file(
        self,
        attachment_id: uuid.UUID,
        *,
        provider: str,
        provider_file_id: str,
        mime_type: str | None = None,
        size_bytes: int | None = None,
    ) -> ChatAttachment | None:
        row = await self.get(attachment_id)
        if row is None:
            return None
        row.provider = provider
        row.provider_file_id = provider_file_id
        if mime_type is not None:
            row.mime_type = mime_type
        if size_bytes is not None:
            row.size_bytes = size_bytes
        await self._session.flush()
        return row

    async def insert(
        self,
        *,
        chat_id: uuid.UUID,
        provider: str,
        provider_file_id: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        message_id: uuid.UUID | None = None,
        attachment_id: uuid.UUID | None = None,
        content_hash: str | None = None,
        gist: str | None = None,
        capture_id: uuid.UUID | None = None,
        attachment_role: str | None = None,
        parse_status: str | None = None,
    ) -> ChatAttachment:
        row = ChatAttachment(
            id=attachment_id or uuid.uuid4(),
            chat_id=chat_id,
            message_id=message_id,
            provider=provider,
            provider_file_id=provider_file_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            content_hash=content_hash,
            gist=gist,
            capture_id=capture_id,
            attachment_role=attachment_role,
        )
        if parse_status is not None:
            row.parse_status = parse_status
        self._session.add(row)
        await self._session.flush()
        return row

    async def delete(self, chat_id: uuid.UUID, attachment_id: uuid.UUID) -> ChatAttachment | None:
        row = await self.get(attachment_id)
        if row is None or row.chat_id != chat_id:
            return None
        await self._session.delete(row)
        await self._session.flush()
        return row

    async def link_to_message(self, attachment_ids: list[uuid.UUID], message_id: uuid.UUID) -> None:
        if not attachment_ids:
            return
        result = await self._session.execute(
            select(ChatAttachment).where(ChatAttachment.id.in_(attachment_ids))
        )
        for row in result.scalars().all():
            row.message_id = message_id

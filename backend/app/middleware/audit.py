import logging
import time
from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AuditMiddleware(FunctionMiddleware):
    """Log tool invocations (persistence handled by ChatRunService after agent run)."""

    def __init__(self, db: AsyncSession, *, chat_id: Any | None) -> None:
        self._db = db
        self._chat_id = chat_id

    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        started = time.perf_counter()
        await call_next()
        if self._chat_id is None:
            return
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.debug(
            "tool %s chat=%s duration_ms=%s",
            context.function.name,
            self._chat_id,
            duration_ms,
        )

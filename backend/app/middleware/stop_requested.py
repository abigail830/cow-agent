import asyncio

from agent_framework import AgentContext, AgentMiddleware, MiddlewareTermination


class StopRequestedMiddleware(AgentMiddleware):
    """Stop ReAct loop before the next model/service call when user cancels."""

    def __init__(self, stop_event: asyncio.Event) -> None:
        self._stop = stop_event

    async def process(self, context: AgentContext, call_next) -> None:
        if self._stop.is_set():
            raise MiddlewareTermination("Run cancelled by user")
        await call_next()

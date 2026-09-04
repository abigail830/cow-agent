"""Chat-layer PII / secret redaction — MAF ChatMiddleware."""

from __future__ import annotations

import logging

from agent_framework import ChatContext, ChatMiddleware, Content, Message

from app.platform.guardrails.pii_patterns import redact_sensitive_text

logger = logging.getLogger(__name__)


def _redact_message_contents(message: Message) -> int:
    """Redact text blocks in-place; return substitution count."""
    contents = getattr(message, "contents", None) or []
    total = 0
    for block in contents:
        if not isinstance(block, Content):
            continue
        if getattr(block, "type", None) != "text":
            continue
        text = getattr(block, "text", None)
        if not text:
            continue
        redacted, count = redact_sensitive_text(str(text))
        if count:
            block.text = redacted
            total += count
    return total


class ChatPiiRedactionMiddleware(ChatMiddleware):
    """Redact common secret patterns from chat messages before they reach the model."""

    async def process(self, context: ChatContext, call_next) -> None:
        redacted_blocks = 0
        for message in context.messages or []:
            if not isinstance(message, Message):
                continue
            redacted_blocks += _redact_message_contents(message)

        if redacted_blocks:
            context.metadata["pii_redaction_count"] = redacted_blocks
            logger.info(
                "chat_pii_redaction",
                extra={
                    "audit_event": "chat_pii_redaction",
                    "redaction_count": redacted_blocks,
                    "message_count": len(context.messages or []),
                },
            )

        await call_next()

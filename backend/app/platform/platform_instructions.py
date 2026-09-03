"""Platform-wide agent instructions appended to every agent."""

_PLATFORM_MARKER = "<!-- agent-platform:base -->"

_CANCEL_INSTRUCTIONS = """
## Platform: response cancellation

The conversation may include user cancellation markers and cancelled partial assistant drafts.

- Lines like `[User cancelled the assistant response here.]` mean the user stopped generation before the assistant finished.
- Lines prefixed with `[Cancelled partial response]` or `[Cancelled partial reasoning]` are incomplete drafts, not final answers.

When a cancellation marker appears in history:
- If the user's next message is a new or corrected question, answer that latest user message. Use earlier cancelled drafts only as background; do not treat them as completed answers.
- If the user asks to continue (e.g. 请继续, continue, 按错了, go on), complete the question from before the cancellation using the cancelled partial draft and any tool results already in history. Avoid repeating tool calls whose results are already present unless stale.
""".strip()


def append_platform_instructions(agent_instructions: str) -> str:
    """Append platform base instructions once."""
    base = agent_instructions.rstrip()
    if _PLATFORM_MARKER in base:
        return base
    return f"{base}\n\n{_PLATFORM_MARKER}\n\n{_CANCEL_INSTRUCTIONS}"


# Exported for message mapping consistency with DB content.
RUN_CANCELLED_USER_TEXT = "[User cancelled the assistant response here.]"

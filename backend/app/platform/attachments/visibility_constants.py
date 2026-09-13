"""Shared attachment visibility labels — SSOT for facts, prompts, and code guards."""

from __future__ import annotations

# --- Canonical visibility state values (used in facts block + run_state) ---

VISIBILITY_INLINED = "inlined_this_turn"
VISIBILITY_NOT_INLINED = "not_inlined"
VISIBILITY_SUMMARY_ONLY = "summary_only_in_history"

ALL_VISIBILITY_STATES: frozenset[str] = frozenset(
    {
        VISIBILITY_INLINED,
        VISIBILITY_NOT_INLINED,
        VISIBILITY_SUMMARY_ONLY,
    }
)

# --- Prompt vocabulary (instructions + tool descriptions must reference these) ---

VISIBILITY_INLINED_INSTRUCTION = (
    f"**visibility={VISIBILITY_INLINED}**: pixels or full text are already in the current user message — "
    "answer directly; do **not** call `analyze_image` or `inline_attachment` for that id."
)

VISIBILITY_NOT_INLINED_INSTRUCTION = (
    f"**visibility={VISIBILITY_NOT_INLINED}**: content not in context — choose by task and budget:"
)

VISIBILITY_SUMMARY_ONLY_INSTRUCTION = (
    f"**visibility={VISIBILITY_SUMMARY_ONLY}**: a stub points to earlier full content; "
    "re-inline or pull if you need pixels or verbatim text again."
)

ATTACHMENT_PLATFORM_INSTRUCTIONS_BODY = f"""
## Platform: chat attachments (facts + budget — you choose strategy)

Each run includes an **attachment facts + budget** block (costs, visibility per id).
- {VISIBILITY_INLINED_INSTRUCTION}
- {VISIBILITY_NOT_INLINED_INSTRUCTION}
  - Direct vision / layout / handwriting: `inline_attachment(attachment_id)`
  - Cheaper text summary: `analyze_image` or `map_attachment` per id
  - Verbatim document text: `read_attachment(attachment_id)`
- {VISIBILITY_SUMMARY_ONLY_INSTRUCTION}
- Respect inline budget errors; do not retry `inline_attachment` when over budget.
- Use `search_attachments(query)` when many files exist and you need the right id.
- Do not invent facts missing from visible content or a summary — pull again when needed.
""".strip()

# Tool description fragments (must mention visibility states they gate on)

INLINE_ATTACHMENT_TOOL_DESCRIPTION = (
    "Request direct attachment content in your orchestrator context (image pixels or doc full text path). "
    "Does NOT return bytes in tool_result — content is injected before your next reasoning step. "
    f"Use when visibility={VISIBILITY_NOT_INLINED} and you need direct vision. "
    f"Do NOT call when visibility={VISIBILITY_INLINED} or after a successful inline in this turn."
)

ANALYZE_IMAGE_TOOL_DESCRIPTION = (
    "Worker: analyze a chat image and return a text summary (no raw image bytes). "
    f"Use when visibility={VISIBILITY_NOT_INLINED} and a cheaper summary is enough, or inline budget is tight. "
    f"Do NOT call when visibility={VISIBILITY_INLINED} — answer from visible pixels instead. "
    "For many images, prefer map_attachment per id. For documents, use read_attachment."
)

# Guard responses (hard layer — must tell model how to recover)

GUARD_ALREADY_INLINED_MESSAGE = (
    f"Attachment is already visible (visibility={VISIBILITY_INLINED}). "
    "Answer directly from the image or text already in your context. "
    "Do not retry analyze_image or inline_attachment for this id."
)

GUARD_JUST_INLINED_MESSAGE = (
    "Attachment was just inlined into your context. Answer directly from visible content; "
    "do not retry analyze_image or inline_attachment."
)

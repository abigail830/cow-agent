"""Format memory documents for system prompt injection."""

from __future__ import annotations

import re

_BULLET_RE = re.compile(r"^(\[!\]|-)\s*(.+)$")


def parse_bullets(content: str) -> list[tuple[str, str]]:
    """Return list of (prefix, text) for each non-empty line."""
    rows: list[tuple[str, str]] = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _BULLET_RE.match(line)
        if match:
            rows.append((match.group(1), match.group(2).strip()))
        else:
            rows.append(("-", line))
    return rows


def bullets_to_lines(rows: list[tuple[str, str]]) -> list[str]:
    return [f"{prefix} {text}" if prefix == "[!]" else f"- {text}" for prefix, text in rows]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _trim_rows(rows: list[tuple[str, str]], max_tokens: int) -> list[tuple[str, str]]:
    working = list(rows)
    while working and _estimate_tokens("\n".join(bullets_to_lines(working))) > max_tokens:
        removed = False
        for index, (prefix, _) in enumerate(working):
            if prefix != "[!]":
                working.pop(index)
                removed = True
                break
        if not removed:
            working.pop(0)
    return working


def format_scope_block(scope_label: str, content: str, *, max_tokens: int) -> str:
    rows = parse_bullets(content)
    if not rows:
        return ""
    trimmed = _trim_rows(rows, max_tokens)
    lines = bullets_to_lines(trimmed)
    body = "\n".join(lines)
    return f"<{scope_label}>\n{body}\n</{scope_label}>"


MEMORY_POLICY = """<memory_policy>
Bullet conventions:
- Lines starting with [!] are hard constraints (must follow).
- Lines starting with - in user_preferences are soft style preferences.
- Lines starting with - in agent_context are task-specific facts/defaults.

Precedence:
1. [!] constraints in user_preferences override everything else in memory.
2. agent_context facts/defaults apply to this agent's domain work.
3. For style conflicts, prefer agent_context in this chat.
4. If ambiguous, ask the user.

Do not invent memory not listed below.
</memory_policy>"""


def format_for_injection(
    user_content: str,
    agent_content: str,
    *,
    agent_slug: str,
    max_tokens: int = 1500,
) -> str:
    user_block = format_scope_block("user_preferences", user_content, max_tokens=max_tokens // 2)
    agent_block = format_scope_block(
        "agent_context",
        agent_content,
        max_tokens=max_tokens // 2,
    )
    if agent_block:
        agent_block = agent_block.replace(
            "<agent_context>",
            f'<agent_context agent="{agent_slug}">',
            1,
        )

    parts = [MEMORY_POLICY]
    if user_block:
        parts.append(user_block)
    if agent_block:
        parts.append(agent_block)
    if len(parts) == 1:
        return ""
    return "\n\n".join(parts)


def validate_line(line: str) -> str:
    """Normalize a single bullet line for storage."""
    text = line.strip()
    if not text:
        raise ValueError("Empty memory line")
    if text.startswith("[!]"):
        body = text[3:].strip()
        if not body:
            raise ValueError("Constraint line needs content after [!]")
        return f"[!] {body}"
    if text.startswith("-"):
        body = text[1:].strip()
        if not body:
            raise ValueError("Bullet line needs content after -")
        return f"- {body}"
    return f"- {text}"

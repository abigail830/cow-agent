from __future__ import annotations


def truncate_chars(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0:
        return "", bool(text)
    if len(text) <= max_chars:
        return text, False
    if max_chars < 80:
        return text[:max_chars], True
    head = max_chars // 2
    tail = max_chars - head - 40
    if tail < 0:
        tail = 0
    omitted = len(text) - head - tail
    marker = f"\n… [truncated {omitted} chars] …\n"
    return f"{text[:head]}{marker}{text[-tail:] if tail else ''}", True

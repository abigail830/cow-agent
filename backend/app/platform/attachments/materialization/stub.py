"""Stub text and force re-read detection for attachment materialization."""

from __future__ import annotations

FORCE_REREAD_PHRASES: tuple[str, ...] = (
    "重新读取",
    "再看一遍",
    "重新查看原文",
    "re-read attachment",
    "re-read",
)


def user_requests_force_reread(user_text: str) -> bool:
    lowered = (user_text or "").lower()
    for phrase in FORCE_REREAD_PHRASES:
        if phrase.lower() in lowered:
            return True
    return False


def format_attachment_stub(
    *,
    filename: str,
    attachment_id: str,
    first_turn_sequence: int,
    content_hash: str = "",
    hash_changed: bool = False,
) -> str:
    hash_hint = ""
    if content_hash:
        short = content_hash.removeprefix("sha256:")[:8]
        hash_hint = f" hash={short}"
    version_note = "\n注意：该附件内容已更新，以下为最新版本。" if hash_changed else ""
    return (
        "[Attachment reference]\n"
        f"用户再次引用「{filename}」(id={attachment_id}{hash_hint})。\n"
        f"完整内容已在第 {first_turn_sequence} 轮 user 消息中提供。\n"
        "如需重新查看原文，请在消息中说明「重新读取/再看一遍」。"
        f"{version_note}"
    )


def format_compaction_placeholder(
    *,
    filename: str,
    attachment_id: str,
    kind: str,
) -> str:
    return (
        "[Attachment compacted]\n"
        f"「{filename}」(id={attachment_id}) 的完整 {kind} 内容已从上下文窗口移除以节省空间。\n"
        "再次 @ 该附件可重新加载完整内容。"
    )

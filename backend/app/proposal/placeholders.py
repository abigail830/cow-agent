"""Resolve template.yaml placeholders from draft facts and fee tables."""

from __future__ import annotations

from typing import Any

from app.proposal.loaders import load_package_briefs_index, load_template_yaml, read_static_block


def _facts_value(draft: dict[str, Any], dotted_path: str) -> Any:
    if not dotted_path.startswith("/facts/"):
        return None
    value: Any = draft.get("facts") or {}
    for part in dotted_path[len("/facts/") :].split("/"):
        if not part:
            continue
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def selected_package_names(draft: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for section in (draft.get("document") or {}).get("sections") or []:
        if section.get("kind") != "fee_section":
            continue
        for table in section.get("tables") or []:
            title = str(table.get("title") or "").strip()
            source = table.get("source") or {}
            package_id = str(source.get("package_id") or "").strip()
            key = package_id or title
            if not key or key in seen:
                continue
            seen.add(key)
            names.append(title or package_id)
    return names


def _resolve_placeholder_value(
    spec: dict[str, Any],
    *,
    draft: dict[str, Any],
) -> str:
    draft_path = str(spec.get("draft_path") or "").strip()
    if draft_path == "derived":
        token = str(spec.get("token") or "")
        if token == "{{selected_packages_bullet_list}}":
            names = selected_package_names(draft)
            if not names:
                return str(spec.get("empty") or "—")
            return "\n".join(f"- {name}" for name in names)
        return ""

    value = _facts_value(draft, draft_path)
    if value not in (None, ""):
        return str(value)
    if spec.get("default") is not None:
        return str(spec["default"])
    return ""


def apply_template_placeholders(
    text: str,
    draft: dict[str, Any],
    template_id: str,
    context: str,
) -> str:
    """Replace tokens declared under template placeholders.{context}."""
    if not text or not template_id:
        return text
    tpl = load_template_yaml(template_id)
    specs = (tpl.get("placeholders") or {}).get(context) or []
    if not isinstance(specs, list):
        return text
    result = text
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        token = str(spec.get("token") or "")
        if not token or token not in result:
            continue
        result = result.replace(token, _resolve_placeholder_value(spec, draft=draft))
    return result


def placeholder_context_for_section(section: dict[str, Any], *, template_id: str = "") -> str | None:
    section_id = str(section.get("id") or "")
    if section_id == "introduction":
        return "introduction"
    if section.get("kind") == "fee_section":
        return "fee_table"
    if template_id:
        specs = load_template_yaml(template_id).get("placeholders") or {}
        if section_id in specs:
            return section_id
    return None


def resolve_section_source_content(
    draft: dict[str, Any],
    section: dict[str, Any],
    *,
    template_id: str,
) -> str:
    """Load source-backed section text and apply placeholders."""
    edit_state = (section.get("edit_state") or {}).get("content")
    source = section.get("source") or {}
    file_ref = source.get("file")
    content = str(section.get("content") or "")
    if edit_state == "source" and file_ref:
        try:
            content = read_static_block(template_id, str(file_ref))
        except OSError:
            content = str(section.get("content") or "")
    context = placeholder_context_for_section(section, template_id=template_id)
    if context:
        content = apply_template_placeholders(content, draft, template_id, context)
    return content.strip()


def _brief_index_entry(
    fee_section: dict[str, Any],
    template_id: str,
    package_id: str,
) -> tuple[dict[str, Any], str] | None:
    index_ref = str((fee_section.get("package_briefs") or {}).get("index") or "").strip()
    if not index_ref:
        return None
    try:
        index = load_package_briefs_index(template_id, index_ref)
    except (OSError, ValueError):
        return None
    entry = index.get(package_id)
    if not isinstance(entry, dict):
        return None
    file_ref = str(entry.get("file") or "").strip()
    if not file_ref:
        return None
    return entry, file_ref


def build_table_brief(
    draft: dict[str, Any],
    fee_section: dict[str, Any],
    *,
    template_id: str,
    package_id: str,
    package_name: str,
) -> dict[str, Any] | None:
    """Materialize one editable package brief for fee_section.tables[].brief."""
    resolved = _brief_index_entry(fee_section, template_id, package_id)
    if resolved is None:
        return None
    entry, file_ref = resolved
    content = ""
    try:
        content = read_static_block(template_id, file_ref).strip()
    except OSError:
        content = ""
    if content:
        content = apply_template_placeholders(content, draft, template_id, "fee_table")
    return {
        "kind": "markdown_block",
        "content": content,
        "edit_state": {"content": "source" if content else "empty"},
        "source": {
            "type": "template_package_brief",
            "package_id": package_id,
            "file": file_ref,
        },
        "policy": {"editable": True, "removable": True},
    }


def resolve_table_brief_content(
    draft: dict[str, Any],
    brief: dict[str, Any],
    *,
    template_id: str,
) -> str:
    edit_state = (brief.get("edit_state") or {}).get("content")
    source = brief.get("source") or {}
    file_ref = source.get("file")
    content = str(brief.get("content") or "")
    if edit_state == "source" and file_ref:
        try:
            content = read_static_block(template_id, str(file_ref)).strip()
        except OSError:
            content = str(brief.get("content") or "")
    return apply_template_placeholders(content, draft, template_id, "fee_table").strip()


def render_fee_section_briefs(
    draft: dict[str, Any],
    *,
    template_id: str,
    fee_section: dict[str, Any],
) -> str:
    """Concatenate package briefs from fee_section.tables[] in list order."""
    parts: list[str] = []
    for table in fee_section.get("tables") or []:
        if not isinstance(table, dict):
            continue
        brief = table.get("brief")
        if not isinstance(brief, dict):
            continue
        body = resolve_table_brief_content(draft, brief, template_id=template_id)
        if body:
            parts.append(body)
    return "\n\n".join(parts).strip()


def _intro_content_edit_state(intro: dict[str, Any]) -> str:
    edit_state = intro.get("edit_state")
    if isinstance(edit_state, dict):
        return str(edit_state.get("content") or "")
    if isinstance(edit_state, str):
        return edit_state
    return ""


def _sync_intro_markdown_block(
    draft: dict[str, Any],
    intro: dict[str, Any],
    *,
    template_id: str,
    placeholder_context: str = "fee_table",
) -> None:
    if _intro_content_edit_state(intro) != "source":
        return
    source = intro.get("source") or {}
    file_ref = source.get("file")
    if not file_ref:
        return
    try:
        content = read_static_block(template_id, str(file_ref)).strip()
    except OSError:
        content = str(intro.get("content") or "")
    intro["content"] = apply_template_placeholders(content, draft, template_id, placeholder_context)


def _sync_fee_section_intro(
    draft: dict[str, Any],
    fee_section: dict[str, Any],
    *,
    template_id: str,
) -> None:
    intro = fee_section.get("intro") or {}
    if not isinstance(intro, dict):
        return
    _sync_intro_markdown_block(draft, intro, template_id=template_id, placeholder_context="fee_table")


def sync_draft_template_placeholders(draft: dict[str, Any]) -> dict[str, Any]:
    """Refresh source-backed sections after packages or client facts change."""
    template_id = str((draft.get("meta") or {}).get("template_id") or "").strip()
    if not template_id:
        return draft
    for section in (draft.get("document") or {}).get("sections") or []:
        if section.get("kind") == "fee_section":
            _sync_fee_section_intro(draft, section, template_id=template_id)
            for table in section.get("tables") or []:
                if not isinstance(table, dict):
                    continue
                brief = table.get("brief")
                if not isinstance(brief, dict):
                    continue
                if (brief.get("edit_state") or {}).get("content") != "source":
                    continue
                brief["content"] = resolve_table_brief_content(
                    draft,
                    brief,
                    template_id=template_id,
                )
            continue
        if section.get("kind") == "derived_section":
            intro = section.get("intro") or {}
            if isinstance(intro, dict):
                _sync_intro_markdown_block(draft, intro, template_id=template_id, placeholder_context="fee_table")
            continue
        if section.get("kind") != "markdown_block":
            continue
        edit_state = (section.get("edit_state") or {}).get("content")
        if edit_state != "source":
            continue
        resolved = resolve_section_source_content(draft, section, template_id=template_id)
        section["content"] = resolved
    return draft

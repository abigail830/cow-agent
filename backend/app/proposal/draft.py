"""Editable proposal draft state.

Draft state is the structured document the user edits. Templates and sources
materialize it; renderers consume it directly.
"""

from __future__ import annotations

import copy
import re
from typing import Any

import jsonpatch

from app.proposal.fee_row import (
    first_invoice_row_amount,
    is_adhoc_fee_row,
    materialize_mdm_fee_row,
    render_row_dto,
    resolve_fee_row_display,
    remove_fee_rows_by_sku,
    validate_fee_row_patches,
)
from app.proposal.fee_table import render_frequency_table, render_simple_table
from app.proposal.fee_table import (
    payment_summary_footer,
    render_first_invoice_table,
    render_payment_options_table,
    row_total_annualized,
    sum_group_columns,
)
from app.proposal.loaders import (
    load_template_yaml,
    read_static_block,
)
from app.proposal.preview import proposal_state_fingerprint

PROPOSAL_DRAFT_KEY = "proposal_draft"


DEFAULT_CLIENT_FACTS = {
    "company_name": None,
    "short_name": None,
    "address": None,
    "contract_name": None,
    "contract_title": None,
    "contract_email": None,
}


class DraftPatchError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def empty_proposal_draft() -> dict[str, Any]:
    return {
        "version": 1,
        "meta": {"template_id": None, "title": None},
        "facts": {"client": copy.deepcopy(DEFAULT_CLIENT_FACTS)},
        "document": {"sections": []},
    }


def load_proposal_draft_from_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    draft = payload.get(PROPOSAL_DRAFT_KEY)
    return copy.deepcopy(draft) if isinstance(draft, dict) and draft else None


def _client_value(client: dict[str, Any], dotted_path: str) -> Any:
    if not dotted_path.startswith("client."):
        return None
    value: Any = client
    for part in dotted_path.split(".")[1:]:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _render_draft_title(tpl: dict[str, Any], client: dict[str, Any]) -> str:
    cfg = tpl.get("document_title")
    if isinstance(cfg, str) and cfg.strip():

        def replace(match: re.Match[str]) -> str:
            parts = [part.strip() for part in match.group(1).split("|")]
            for part in parts:
                value = _client_value(client, part)
                if value:
                    return str(value)
            for part in parts:
                if part.startswith("default:"):
                    return part.split(":", 1)[1]
            return ""

        return re.sub(r"\{\{([^}]+)\}\}", replace, cfg.strip())
    if isinstance(cfg, dict):
        prefix = str(cfg.get("prefix") or "Proposal").strip()
        name_fields = cfg.get("name_from") or ["client.company_name", "client.contract_name"]
        for field in name_fields:
            value = _client_value(client, str(field))
            if value:
                return f"{prefix} - {value}" if prefix else str(value)
        if cfg.get("fallback"):
            return str(cfg["fallback"])
        return prefix
    return str(client.get("company_name") or client.get("contract_name") or "Proposal")


def _draft_filename(draft: dict[str, Any]) -> str:
    client = (draft.get("facts") or {}).get("client") or {}
    title = (
        client.get("company_name")
        or client.get("contract_name")
        or (draft.get("meta") or {}).get("title")
        or "proposal"
    )
    safe = re.sub(r'[<>:"/\\|?*]', "-", str(title).strip())
    safe = re.sub(r"\s+", " ", safe).strip()
    return f"{safe}.md" if safe else "proposal.md"


def _section_policy(spec: dict[str, Any]) -> dict[str, Any]:
    editable = bool(spec.get("editable", True))
    return {
        "editable": editable,
        "removable": not bool(spec.get("required")),
        "regenerable": True,
    }


def _copy_section_agent_guidance(section: dict[str, Any], spec: dict[str, Any]) -> None:
    guidance = spec.get("agent_guidance")
    if guidance is None:
        return
    text = str(guidance).strip()
    if text:
        section["agent_guidance"] = text


def _static_section(template_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    source = dict(spec.get("source") or {})
    if not source and spec.get("file"):
        source = {"type": "template_file", "file": spec.get("file")}
    section = {
        "id": str(spec["id"]),
        "kind": "static_block",
        "title": str(spec.get("title") or spec["id"]),
        "enabled": bool(spec.get("default_enabled", spec.get("required", True))),
        "required": bool(spec.get("required")),
        "source": source,
        "policy": _section_policy({**spec, "editable": False}),
    }
    _copy_section_agent_guidance(section, spec)
    return section


def _markdown_section(template_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    source = dict(spec.get("source") or {})
    content = str(spec.get("content") or "")
    file_ref = source.get("file")
    if file_ref and not content:
        try:
            content = read_static_block(template_id, str(file_ref))
        except OSError:
            content = ""
    section = {
        "id": str(spec["id"]),
        "kind": "markdown_block",
        "title": str(spec.get("title") or spec["id"]),
        "enabled": bool(spec.get("default_enabled", spec.get("enabled", True))),
        "required": bool(spec.get("required")),
        "source": source,
        "policy": _section_policy(spec),
        "content": content,
        "edit_state": {"content": "source" if content else "empty"},
    }
    _copy_section_agent_guidance(section, spec)
    return section


def _build_intro_markdown_block(
    template_id: str,
    intro_spec: dict[str, Any] | None,
    *,
    block_id: str = "intro",
    title: str = "Intro",
) -> dict[str, Any] | None:
    """Materialize fee/derived section intro as a standard markdown_block node."""
    if not intro_spec:
        return None
    intro_source = dict(intro_spec.get("source") or {})
    file_ref = intro_source.get("file")
    inline_content = str(intro_spec.get("content") or "").strip()
    if not file_ref and not inline_content:
        return None
    if file_ref and not intro_source.get("type"):
        intro_source["type"] = "template_file"
    content = inline_content
    if file_ref and not content:
        try:
            content = read_static_block(template_id, str(file_ref)).strip()
        except OSError:
            content = ""
    editable = bool(intro_spec.get("editable", True))
    return {
        "id": block_id,
        "kind": "markdown_block",
        "title": title,
        "content": content,
        "source": intro_source,
        "policy": {"editable": editable, "removable": False},
        "edit_state": {"content": "source" if (content or file_ref) else "empty"},
    }


def _fee_section(template_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    section: dict[str, Any] = {
        "id": str(spec["id"]),
        "kind": "fee_section",
        "title": str(spec.get("title") or spec["id"]),
        "enabled": True,
        "required": bool(spec.get("required")),
        "source": {"type": "mdm_selection"},
        "policy": {
            "editable": True,
            "removable": not bool(spec.get("required")),
            "row_addable": True,
            "row_removable": True,
            "regenerable": True,
        },
        "fee_layout": dict(spec.get("fee_layout") or {}),
        "package_briefs": dict(spec.get("package_briefs") or {}),
        "tables": [],
    }
    intro_block = _build_intro_markdown_block(template_id, spec.get("intro") or {})
    if intro_block:
        section["intro"] = intro_block
    _copy_section_agent_guidance(section, spec)
    return section


def _collection_section(spec: dict[str, Any]) -> dict[str, Any]:
    collection_spec = dict(spec.get("collection") or {})
    child_kind = str(collection_spec.get("child_kind") or "").strip().lower()
    section: dict[str, Any] = {
        "id": str(spec["id"]),
        "kind": "collection",
        "title": str(spec.get("title") or spec["id"]),
        "enabled": bool(spec.get("default_enabled", spec.get("required", False))),
        "required": bool(spec.get("required")),
        "source": dict(spec.get("source") or {}),
        "policy": {
            "editable": True,
            "removable": not bool(spec.get("required")),
            "item_editable": True,
            "block_addable": child_kind == "markdown_block",
            "regenerable": True,
        },
        "add_policy": dict(spec.get("add_policy") or {}),
        "render": dict(spec.get("render") or {}),
    }
    if child_kind == "markdown_block":
        section["collection"] = {"child_kind": "markdown_block"}
        section["blocks"] = []
    else:
        section["items"] = []
    _copy_section_agent_guidance(section, spec)
    return section


def new_collection_markdown_block(
    *,
    block_id: str,
    title: str,
    content: str = "",
    edit_state: str = "empty",
) -> dict[str, Any]:
    """Standard markdown_block child for collection.blocks[] (e.g. appendices)."""
    if not str(title or "").strip():
        raise ValueError("collection markdown_block requires a non-empty title")
    return {
        "id": str(block_id).strip(),
        "kind": "markdown_block",
        "title": str(title).strip(),
        "enabled": True,
        "content": str(content or ""),
        "source": {},
        "policy": {"editable": True, "removable": True},
        "edit_state": {"content": edit_state if content.strip() else "empty"},
    }


def _derived_section(template_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    derivation = dict(spec.get("derivation") or {})
    derivation.pop("agent_guidance", None)
    section: dict[str, Any] = {
        "id": str(spec["id"]),
        "kind": "derived_section",
        "title": str(spec.get("title") or spec["id"]),
        "enabled": bool(spec.get("default_enabled", spec.get("required", False))),
        "required": bool(spec.get("required")),
        "source": {"type": "derived"},
        "policy": {
            "editable": False,
            "removable": not bool(spec.get("required")),
            "regenerable": True,
        },
        "derivation": derivation,
        "overrides": {},
    }
    intro_block = _build_intro_markdown_block(template_id, spec.get("intro") or {})
    if intro_block:
        section["intro"] = intro_block
    _copy_section_agent_guidance(section, spec)
    return section


def materialize_draft(
    *,
    template_id: str,
    client: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not template_id:
        raise ValueError("template_id is required")

    tpl = load_template_yaml(template_id)
    sections = list(tpl.get("sections") or [])
    if not sections:
        raise ValueError(f"Template {template_id!r} does not define sections")

    draft = empty_proposal_draft()
    draft["meta"]["template_id"] = template_id
    draft["facts"]["client"] = {**copy.deepcopy(DEFAULT_CLIENT_FACTS), **copy.deepcopy(client or {})}
    draft["meta"]["title"] = _render_draft_title(tpl, draft["facts"]["client"])

    materialized: list[dict[str, Any]] = []
    for spec in sections:
        kind = spec.get("kind")
        if kind == "static_block":
            materialized.append(_static_section(template_id, spec))
        elif kind == "markdown_block":
            materialized.append(_markdown_section(template_id, spec))
        elif kind == "fee_section":
            materialized.append(_fee_section(template_id, spec))
        elif kind == "collection":
            materialized.append(_collection_section(spec))
        elif kind == "derived_section":
            materialized.append(_derived_section(template_id, spec))
        else:
            section = {
                "id": str(spec["id"]),
                "kind": str(kind or "section"),
                "title": str(spec.get("title") or spec["id"]),
                "enabled": bool(spec.get("default_enabled", spec.get("required", False))),
                "required": bool(spec.get("required")),
                "source": dict(spec.get("source") or {}),
                "policy": _section_policy(spec),
            }
            _copy_section_agent_guidance(section, spec)
            materialized.append(section)
    draft["document"]["sections"] = materialized
    return draft


def _sections(draft: dict[str, Any]) -> list[dict[str, Any]]:
    doc = draft.setdefault("document", {})
    sections = doc.setdefault("sections", [])
    return sections if isinstance(sections, list) else []


def find_section(draft: dict[str, Any], section_id: str) -> dict[str, Any] | None:
    for section in _sections(draft):
        if section.get("id") == section_id:
            return section
    return None


def _first_fee_section(draft: dict[str, Any]) -> dict[str, Any]:
    for section in _sections(draft):
        if section.get("kind") == "fee_section":
            return section
    raise ValueError("Draft has no fee_section")


def template_fee_section_spec(template_id: str, section_id: str) -> dict[str, Any]:
    tpl = load_template_yaml(template_id)
    for spec in tpl.get("sections") or []:
        if str(spec.get("id") or "") == section_id and spec.get("kind") == "fee_section":
            return dict(spec)
    return {}


# Keys stored on draft fee_section.fee_layout — draft instance wins over template.
_INSTANCE_LAYOUT_KEYS = frozenset(
    {
        "table_style",
        "column_widths",
        "column_labels",
        "amount_column_label",
        "empty_cell",
        "service_columns",
        "show_recurring",
        "show_line_amount",
        "show_billing_frequency",
        "group_by",
        "tables_heading",
        "footnotes",
        "currency",
    }
)


def _effective_fee_layout(draft: dict[str, Any], section: dict[str, Any]) -> dict[str, Any]:
    """Merge template defaults with draft instance layout; draft presentation keys win."""
    draft_layout = dict(section.get("fee_layout") or {})
    template_id = str((draft.get("meta") or {}).get("template_id") or "").strip()
    if not template_id:
        return draft_layout
    spec = template_fee_section_spec(template_id, str(section.get("id") or ""))
    tpl_layout = dict(spec.get("fee_layout") or {})
    merged = {**tpl_layout, **draft_layout}
    for key in _INSTANCE_LAYOUT_KEYS:
        if key in draft_layout and draft_layout[key] is not None:
            merged[key] = draft_layout[key]
    return merged


def _catalog_scope_for_draft(draft: dict[str, Any]) -> tuple[str | None, str | None]:
    template_id = str((draft.get("meta") or {}).get("template_id") or "").strip()
    if not template_id:
        return None, None
    try:
        from app.mdm.catalog_scope import resolve_catalog_scope

        scope = resolve_catalog_scope(template_id=template_id)
        return scope.get("jurisdiction"), scope.get("bu")
    except Exception:
        return None, None


def _refresh_draft_fee_row_displays(draft: dict[str, Any]) -> dict[str, Any]:
    from app.proposal.fee_row import iter_fee_rows

    updated = copy.deepcopy(draft)
    for section, _table, row in iter_fee_rows(updated):
        layout = _effective_fee_layout(updated, section)
        row["display"] = resolve_fee_row_display(row, layout=layout)
    return updated


def add_package_to_draft(draft: dict[str, Any], package: dict[str, Any], services: list[dict[str, Any]]) -> dict[str, Any]:
    updated = copy.deepcopy(draft)
    package_id = str(package.get("package_id") or "").strip()
    if not package_id:
        raise ValueError("package.package_id is required")
    if not services:
        raise ValueError("services are required")

    fee_section = _first_fee_section(updated)
    layout = _effective_fee_layout(updated, fee_section)
    jurisdiction, bu = _catalog_scope_for_draft(updated)
    rows = [
        materialize_mdm_fee_row(
            service,
            package_id=package_id,
            layout=layout,
            jurisdiction=jurisdiction,
            bu=bu,
        )
        for service in services
    ]
    if not rows:
        return updated

    existing_table: dict[str, Any] | None = None
    for table in fee_section.get("tables") or []:
        if not isinstance(table, dict):
            continue
        if str((table.get("source") or {}).get("package_id") or "").strip() == package_id:
            existing_table = table
            break

    if existing_table is not None:
        existing_skus = {
            str((row.get("source") or {}).get("sku") or "").strip()
            for row in existing_table.get("rows") or []
            if isinstance(row, dict)
        }
        new_rows = [
            row
            for row in rows
            if str((row.get("source") or {}).get("sku") or "").strip() not in existing_skus
        ]
        if new_rows:
            existing_table.setdefault("rows", []).extend(new_rows)
        if existing_table.get("brief") is None:
            template_id = str((updated.get("meta") or {}).get("template_id") or "").strip()
            from app.proposal.placeholders import build_table_brief

            brief_block = build_table_brief(
                updated,
                fee_section,
                template_id=template_id,
                package_id=package_id,
                package_name=str(package.get("package_name") or package_id),
            )
            if brief_block:
                existing_table["brief"] = brief_block
        from app.proposal.placeholders import sync_draft_template_placeholders

        return sync_draft_template_placeholders(updated)

    template_id = str((updated.get("meta") or {}).get("template_id") or "").strip()
    from app.proposal.placeholders import build_table_brief, sync_draft_template_placeholders

    table: dict[str, Any] = {
        "id": f"table_{package_id}",
        "kind": "fee_table",
        "title": package.get("package_name") or package_id,
        "source": {"type": "mdm_package", "package_id": package_id},
        "policy": {
            "editable": True,
            "removable": True,
            "row_addable": True,
            "row_removable": True,
        },
        "rows": rows,
    }
    brief_block = build_table_brief(
        updated,
        fee_section,
        template_id=template_id,
        package_id=package_id,
        package_name=str(package.get("package_name") or package_id),
    )
    if brief_block:
        table["brief"] = brief_block
    fee_section.setdefault("tables", []).append(table)
    return sync_draft_template_placeholders(updated)


def add_services_to_draft(
    draft: dict[str, Any],
    services: list[dict[str, Any]],
    *,
    table_id: str | None = None,
    table_title: str = "Additional services",
) -> dict[str, Any]:
    updated = copy.deepcopy(draft)
    if not services:
        raise ValueError("services are required")
    fee_section = _first_fee_section(updated)
    layout = _effective_fee_layout(updated, fee_section)
    jurisdiction, bu = _catalog_scope_for_draft(updated)
    rows = []
    for service in services:
        if not service.get("sku"):
            raise ValueError("service.sku is required")
        rows.append(
            materialize_mdm_fee_row(
                service,
                package_id=None,
                layout=layout,
                jurisdiction=jurisdiction,
                bu=bu,
            )
        )
    tables = fee_section.setdefault("tables", [])
    target = None
    if table_id:
        target = next((table for table in tables if table.get("id") == table_id), None)
    if target is None:
        target = next((table for table in tables if table.get("id") == "table_additional_services"), None)
    if target is None:
        target = {
            "id": table_id or "table_additional_services",
            "kind": "fee_table",
            "title": table_title,
            "source": {"type": "session"},
            "policy": {
                "editable": True,
                "removable": True,
                "row_addable": True,
                "row_removable": True,
            },
            "rows": [],
        }
        tables.append(target)
    existing_ids = {existing.get("id") for existing in target.setdefault("rows", [])}
    for row in rows:
        if row["id"] not in existing_ids:
            target["rows"].append(row)
            existing_ids.add(row["id"])
    return updated


def enable_draft_section(draft: dict[str, Any], section_id: str, enabled: bool = True) -> dict[str, Any]:
    updated = copy.deepcopy(draft)
    section = find_section(updated, section_id)
    if section is None:
        raise ValueError(f"Draft section not found: {section_id}")
    if not enabled and section.get("required"):
        raise DraftPatchError(f"Required section cannot be disabled: {section_id}")
    section["enabled"] = bool(enabled)
    return updated


def patch_draft(draft: dict[str, Any], patch: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(patch, list):
        raise DraftPatchError("Patch must be a JSON Patch array")
    validate_fee_row_patches(patch)
    try:
        updated = jsonpatch.JsonPatch(patch).apply(copy.deepcopy(draft), in_place=False)
    except jsonpatch.JsonPatchException as exc:
        raise DraftPatchError(str(exc)) from exc
    _validate_draft_policy(updated)
    return _refresh_draft_fee_row_displays(updated)


def _validate_draft_policy(draft: dict[str, Any]) -> None:
    for section in _sections(draft):
        policy = section.get("policy") or {}
        if section.get("required") and section.get("enabled") is False:
            raise DraftPatchError(f"Required section cannot be disabled: {section.get('id')}")
        if policy.get("editable") is False and "content" in section:
            raise DraftPatchError(f"Section is not editable: {section.get('id')}")


def _render_titled_section(section: dict[str, Any], content: str) -> str:
    body = content.strip()
    if not body:
        return ""
    title = str(section.get("title") or section.get("id") or "").strip()
    return f"# {title}\n\n{body}" if title else body


def render_draft_markdown(draft: dict[str, Any]) -> str:
    template_id = str((draft.get("meta") or {}).get("template_id") or "")
    parts: list[str] = []
    for section in _sections(draft):
        if section.get("enabled") is False:
            continue
        kind = section.get("kind")
        if kind == "static_block":
            source = section.get("source") or {}
            file_ref = source.get("file")
            if template_id and file_ref:
                try:
                    content = read_static_block(template_id, str(file_ref)).strip()
                except OSError:
                    content = ""
                if content:
                    parts.append(_render_titled_section(section, content))
        elif kind == "markdown_block":
            from app.proposal.placeholders import resolve_section_source_content

            if template_id:
                content = resolve_section_source_content(draft, section, template_id=template_id)
            else:
                content = str(section.get("content") or "").strip()
            if content:
                parts.append(_render_titled_section(section, content))
        elif kind == "fee_section":
            content = _render_fee_section(draft, section)
            if content:
                parts.append(content)
        elif kind == "collection":
            content = _render_collection(draft, section, template_id=template_id)
            if content:
                parts.append(content)
        elif kind == "derived_section":
            content = _render_derived_section(draft, section)
            if content:
                parts.append(content)
    return "\n\n".join(parts).strip()


def _fee_table_render_groups(draft: dict[str, Any], section: dict[str, Any]) -> list[dict[str, Any]]:
    layout = _effective_fee_layout(draft, section)
    group_by = str(layout.get("group_by") or "").strip().lower()
    groups: list[dict[str, Any]] = []

    for table in section.get("tables") or []:
        rows = list(table.get("rows") or [])
        if not rows:
            continue
        render_rows = [render_row_dto(row) for row in rows]
        package_title = str(table.get("title") or table.get("id") or "Services")

        if group_by != "department":
            groups.append(
                {
                    "group_id": table.get("id"),
                    "display_name": package_title,
                    "rows": render_rows,
                }
            )
            continue

        dept_order: list[str] = []
        dept_rows: dict[str, list[dict[str, Any]]] = {}
        for row in render_rows:
            dept = str(row.get("department_team") or "Services").strip() or "Services"
            if dept not in dept_rows:
                dept_order.append(dept)
                dept_rows[dept] = []
            dept_rows[dept].append(row)

        if len(dept_order) <= 1:
            groups.append(
                {
                    "group_id": table.get("id"),
                    "display_name": package_title,
                    "rows": render_rows,
                }
            )
            continue

        for dept in dept_order:
            groups.append(
                {
                    "group_id": f"{table.get('id')}_{dept}",
                    "display_name": f"{package_title} — {dept}",
                    "rows": dept_rows[dept],
                }
            )

    return groups


def _render_fee_section(draft: dict[str, Any], section: dict[str, Any]) -> str:
    groups = _fee_table_render_groups(draft, section)
    if not groups:
        return ""
    layout = _effective_fee_layout(draft, section)
    currency = layout.get("currency")
    from app.proposal.fee_table import (
        fee_column_widths,
        render_fee_table_by_style,
        service_column_flags,
    )
    from app.proposal.footnotes import apply_footnote_numbers, collect_footnotes, render_footnotes_footer

    service_columns = service_column_flags(layout)
    aggregate_footnotes = layout.get("footnotes") == "aggregate"
    all_rows = [row for group in groups for row in group.get("rows") or []]
    footnote_entries = collect_footnotes(all_rows) if aggregate_footnotes else []
    if footnote_entries:
        apply_footnote_numbers(all_rows, footnote_entries)

    title = str(section.get("title") or "Solution and professional fees")
    parts = [f"# {title}"]
    intro = ((section.get("intro") or {}).get("content") or "").strip()
    if intro:
        parts.extend([intro, ""])
    template_id = str((draft.get("meta") or {}).get("template_id") or "")
    from app.proposal.placeholders import render_fee_section_briefs

    briefs = render_fee_section_briefs(draft, template_id=template_id, fee_section=section)
    if briefs:
        parts.extend([briefs, ""])
    tables_heading = str(layout.get("tables_heading") or "").strip()
    if tables_heading:
        parts.extend([f"## {tables_heading}", ""])
    table_style = str(layout.get("table_style") or "simple")
    column_widths = fee_column_widths(layout, table_style)
    parts.append(
        render_fee_table_by_style(
            table_style,
            groups,
            layout=layout,
            currency=currency or "",
            service_columns=service_columns,
            column_widths=column_widths,
        )
    )
    if footnote_entries:
        parts.append(render_footnotes_footer(footnote_entries))
    return "\n\n".join(part for part in parts if part != "")


def _render_markdown_block_node(
    draft: dict[str, Any],
    block: dict[str, Any],
    *,
    template_id: str,
) -> str:
    if block.get("enabled") is False:
        return ""
    from app.proposal.placeholders import resolve_section_source_content

    if template_id:
        content = resolve_section_source_content(draft, block, template_id=template_id)
    else:
        content = str(block.get("content") or "").strip()
    if not content:
        return ""
    title = str(block.get("title") or block.get("id") or "").strip()
    if not title:
        return content
    return _render_titled_section({"title": title}, content)


def _render_collection(
    draft: dict[str, Any],
    section: dict[str, Any],
    *,
    template_id: str,
) -> str:
    blocks = section.get("blocks")
    if isinstance(blocks, list) and blocks:
        render_cfg = section.get("render") or {}
        block_as_chapter = render_cfg.get("block_as_chapter", True)
        parts: list[str] = []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if str(block.get("kind") or "") != "markdown_block":
                continue
            rendered = _render_markdown_block_node(draft, block, template_id=template_id)
            if rendered:
                parts.append(rendered)
        if not parts:
            return ""
        if block_as_chapter:
            return "\n\n".join(parts)
        title = str(section.get("title") or section.get("id"))
        return f"# {title}\n\n" + "\n\n".join(parts)

    if not section.get("items"):
        return ""
    title = str(section.get("title") or section.get("id"))
    body = []
    for item in section.get("items") or []:
        item_title = str(item.get("title") or "").strip()
        item_body = str(item.get("body") or item.get("content") or "").strip()
        if item_title:
            body.append(f"### {item_title}")
        if item_body:
            body.append(item_body)
    return f"# {title}\n\n" + "\n\n".join(body) if body else ""


def _derive_first_invoice_lines(
    draft: dict[str, Any],
    fee_section: dict[str, Any],
    section: dict[str, Any],
) -> list[dict[str, Any]]:
    layout = _effective_fee_layout(draft, fee_section)
    exclude_cfg = (section.get("derivation") or {}).get("exclude") or {}
    lines: list[dict[str, Any]] = []
    for table in fee_section.get("tables") or []:
        if not isinstance(table, dict):
            continue
        for row in table.get("rows") or []:
            if not isinstance(row, dict):
                continue
            if is_adhoc_fee_row(row, exclude_cfg if isinstance(exclude_cfg, dict) else {}):
                continue
            amount = first_invoice_row_amount(row, layout)
            if amount is None or amount <= 0:
                continue
            display = row.get("display") if isinstance(row.get("display"), dict) else {}
            label = str(display.get("preview_primary") or "").strip()
            if not label:
                source = row.get("source") if isinstance(row.get("source"), dict) else {}
                label = str(source.get("service_name") or row.get("id") or "").strip()
            if not label:
                continue
            lines.append({"label": label, "price": amount})
    return lines


def _render_derived_section(draft: dict[str, Any], section: dict[str, Any]) -> str:
    derivation = section.get("derivation") or {}
    deriv_type = str(derivation.get("type") or "").strip()

    if deriv_type == "first_invoice_from_fee_tables":
        source_section_id = str(derivation.get("source_section") or "solution_and_fees")
        fee_section = find_section(draft, source_section_id)
        if not fee_section or fee_section.get("kind") != "fee_section":
            return ""
        lines = _derive_first_invoice_lines(draft, fee_section, section)
        title = str(section.get("title") or "Estimated first invoice value")
        layout = _effective_fee_layout(draft, fee_section)
        currency = str(layout.get("currency") or "")
        tax = derivation.get("tax") if isinstance(derivation.get("tax"), dict) else {}
        parts = [f"# {title}", ""]
        parts.append(render_first_invoice_table(lines, currency=currency, tax=tax))
        return "\n".join(part for part in parts if part != "").strip()

    if deriv_type != "payment_options_from_fee_tables":
        return ""

    source_section_id = str(derivation.get("source_section") or "solution_and_fees")
    fee_section = find_section(draft, source_section_id)
    if not fee_section or fee_section.get("kind") != "fee_section":
        return ""

    options = _derive_payment_options(draft, fee_section, section)
    if not options:
        return ""

    title = str(section.get("title") or "Fee summary")
    currency = str(_effective_fee_layout(draft, fee_section).get("currency") or "")
    parts = [f"# {title}"]

    intro_content = str(((section.get("intro") or {}).get("content") or "")).strip()
    intro_source = (section.get("intro") or {}).get("source") or {}
    template_id = str((draft.get("meta") or {}).get("template_id") or "")
    file_ref = intro_source.get("file")
    if not intro_content and template_id and file_ref:
        try:
            intro_content = read_static_block(template_id, str(file_ref)).strip()
        except OSError:
            intro_content = ""
    if intro_content:
        parts.extend([intro_content, ""])

    parts.append(render_payment_options_table(options, currency=currency))
    return "\n\n".join(part for part in parts if part != "")


def _derive_payment_options(
    draft: dict[str, Any],
    fee_section: dict[str, Any],
    payment_section: dict[str, Any],
) -> list[dict[str, Any]]:
    default_rows: list[dict[str, Any]] = []
    layout = _effective_fee_layout(draft, fee_section)
    for index, table in enumerate(fee_section.get("tables") or [], 1):
        fee_rows = [render_row_dto(row) for row in table.get("rows") or []]
        if not fee_rows:
            continue
        totals = sum_group_columns(fee_rows)
        default_rows.append(
            {
                "group_id": table.get("id") or f"table_{index}",
                "label": table.get("title") or f"{index}. Services",
                **totals,
                "total_annualized": row_total_annualized(totals),
            }
        )

    if not default_rows:
        return []

    default_option = {
        "option_id": "option_a",
        "label": "Payment Option A",
        "rows": default_rows,
        "summary": payment_summary_footer(default_rows),
    }

    options_spec = payment_section.get("options") or []
    overrides = payment_section.get("overrides") or {}
    if not options_spec:
        if isinstance(overrides, dict) and overrides:
            options = []
            for option_id, override in overrides.items():
                option = {
                    **default_option,
                    "option_id": str(option_id),
                    "label": str(option_id).replace("_", " ").title(),
                    "rows": [dict(row) for row in default_rows],
                }
                options.append(_apply_draft_payment_overrides(option, override if isinstance(override, dict) else {}))
            return options
        return [_apply_draft_payment_overrides(default_option, {})]

    options: list[dict[str, Any]] = []
    for spec in options_spec:
        if not isinstance(spec, dict):
            continue
        option = {
            "option_id": spec.get("option_id") or default_option["option_id"],
            "label": spec.get("label") or default_option["label"],
            "rows": _merge_draft_payment_rows(spec.get("rows") or [], default_rows),
        }
        option["summary"] = payment_summary_footer(option["rows"])
        overrides = (payment_section.get("overrides") or {}).get(option["option_id"]) or {}
        options.append(_apply_draft_payment_overrides(option, overrides))
    return options


def _merge_draft_payment_rows(
    row_specs: list[dict[str, Any]],
    default_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not row_specs:
        return [dict(row) for row in default_rows]
    defaults = {
        str(row.get("group_id")): row for row in default_rows if row.get("group_id")
    }
    rows: list[dict[str, Any]] = []
    for spec in row_specs:
        base = dict(defaults.get(str(spec.get("group_id")), {}))
        base.update({key: value for key, value in spec.items() if value is not None})
        base["total_annualized"] = row_total_annualized(base)
        rows.append(base)
    return rows


def _apply_draft_payment_overrides(
    option: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    if not overrides:
        return option
    updated = dict(option)
    if overrides.get("label"):
        updated["label"] = overrides["label"]
    row_overrides = overrides.get("rows") or {}
    if isinstance(row_overrides, list):
        rows = _aggregate_payment_override_rows(row_overrides, option.get("rows") or [])
        rows = [row for row in rows if row]
        if rows:
            updated["rows"] = rows
            updated["summary"] = payment_summary_footer(rows)
            return updated
        row_overrides = {}
    rows: list[dict[str, Any]] = []
    for row in option.get("rows") or []:
        patch = row_overrides.get(row.get("group_id")) or {}
        merged = {**row, **{key: value for key, value in patch.items() if value is not None}}
        merged["total_annualized"] = row_total_annualized(merged)
        rows.append(merged)
    updated["rows"] = rows
    updated["summary"] = payment_summary_footer(rows)
    return updated


def _aggregate_payment_override_rows(
    row_overrides: list[Any],
    default_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    defaults = {
        str(row.get("group_id")): row
        for row in default_rows
        if row.get("group_id")
    }
    fallback_group_id = str(default_rows[0].get("group_id")) if len(default_rows) == 1 and default_rows[0].get("group_id") else None
    aggregates: dict[str, dict[str, Any]] = {}

    for raw_row in row_overrides:
        if not isinstance(raw_row, dict):
            continue
        payment_row = _payment_row_from_override_row(raw_row)
        group_id = str(raw_row.get("group_id") or raw_row.get("table_id") or "")
        if group_id not in defaults:
            group_id = fallback_group_id or group_id or "summary"
        base = defaults.get(group_id) or {}
        aggregate = aggregates.setdefault(
            group_id,
            {
                "group_id": group_id,
                "label": base.get("label") or payment_row.get("label") or "Summary",
                "monthly": 0.0,
                "quarterly": 0.0,
                "annual": 0.0,
                "once_off": 0.0,
            },
        )
        for key in ("monthly", "quarterly", "annual", "once_off"):
            aggregate[key] = float(aggregate.get(key) or 0) + float(payment_row.get(key) or 0)

    rows = list(aggregates.values())
    for row in rows:
        row["total_annualized"] = row_total_annualized(row)
    return rows


def _payment_row_from_override_row(row: dict[str, Any]) -> dict[str, Any]:
    price = row.get("price") if isinstance(row.get("price"), dict) else {}
    amount = price.get("amount", row.get("amount"))
    try:
        value = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        value = None
    frequency = str(price.get("frequency") or row.get("billing_frequency") or row.get("frequency") or "ONE_TIME").upper()
    payment_row = {
        "group_id": row.get("group_id") or row.get("sku") or row.get("id"),
        "label": row.get("label") or row.get("service_name") or row.get("sku") or row.get("id"),
        "monthly": float(row.get("monthly") or 0),
        "quarterly": float(row.get("quarterly") or 0),
        "annual": float(row.get("annual") or 0),
        "once_off": float(row.get("once_off") or 0),
    }
    if value is not None:
        if frequency == "MONTHLY":
            payment_row["monthly"] = value
        elif frequency == "QUARTERLY":
            payment_row["quarterly"] = value
        elif frequency == "ANNUALLY":
            payment_row["annual"] = value
        else:
            payment_row["once_off"] = value
    payment_row["total_annualized"] = row_total_annualized(payment_row)
    return payment_row


def build_draft_preview(draft: dict[str, Any]) -> dict[str, Any]:
    markdown = render_draft_markdown(draft)
    title = str((draft.get("meta") or {}).get("title") or "Proposal draft")
    preview: dict[str, Any] = {
        "status": "ok" if markdown else "empty",
        "title": title,
        "markdown": markdown,
        "filename": _draft_filename(draft),
        "state_fingerprint": proposal_state_fingerprint(draft),
        "completeness": {
            "missing_required": [],
            "ready_to_preview": bool(markdown),
            "ready_to_generate": bool(markdown),
        },
    }
    from app.proposal.export_service import word_export_status

    preview["export"] = {"word": word_export_status(draft if draft else None)}
    return preview

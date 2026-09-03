"""Proposal composer builtin tools."""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Annotated, Any

from agent_framework import tool

from app.mdm.catalog_scope import resolve_catalog_scope
from app.mdm.catalog_service import get_package_services, run_catalog_query
from app.proposal.artifact_spec import ArtifactKind, ArtifactSpec
from app.proposal.context import get_run_proposal_state
from app.proposal.draft import (
    DraftPatchError,
    add_package_to_draft,
    add_services_to_draft,
    build_draft_preview,
    enable_draft_section,
    materialize_draft,
    patch_draft,
    render_draft_markdown,
)
from app.proposal.fee_row import remove_fee_rows_by_sku
from app.proposal.export_service import ProposalExportError, generate_proposal_docx
from app.proposal.loaders import load_templates, read_knowledge_file
from app.proposal.paths import KNOWLEDGE_ROOT, PERIPHERAL_ROOT, TEMPLATES_ROOT
from app.proposal.storage import new_artifact_id, save_markdown

_PREVIEW_CHAR_LIMIT = 1200
logger = logging.getLogger(__name__)


def _resolve_pointer(state: dict[str, Any], pointer: str) -> Any:
    if pointer == "":
        return state
    if not pointer.startswith("/"):
        raise ValueError("JSON Pointer must start with '/'.")
    value: Any = state
    for raw_part in pointer.split("/")[1:]:
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            value = value[int(part)]
        elif isinstance(value, dict):
            value = value[part]
        else:
            raise ValueError(f"Cannot resolve through non-container at {part!r}.")
    return value


def _decode_json_string(value: Any, field_name: str) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be JSON object/array data, not an invalid JSON string") from exc


def _coerce_object(value: Any, field_name: str) -> dict[str, Any]:
    decoded = _decode_json_string(value, field_name)
    if not isinstance(decoded, dict):
        raise ValueError(f"{field_name} must be an object")
    return decoded


def _coerce_object_list(value: Any, field_name: str) -> list[dict[str, Any]]:
    decoded = _decode_json_string(value, field_name)
    if isinstance(decoded, dict):
        return [decoded]
    if not isinstance(decoded, list):
        raise ValueError(f"{field_name} must be an array of objects")
    bad_index = next((idx for idx, item in enumerate(decoded) if not isinstance(item, dict)), None)
    if bad_index is not None:
        raise ValueError(f"{field_name}[{bad_index}] must be an object")
    return decoded


def _is_allowed_knowledge_path(rel: str, full: Path) -> bool:
    """peripheral/* and template contracts/blocks under knowledge/."""
    peripheral = PERIPHERAL_ROOT.resolve()
    templates = TEMPLATES_ROOT.resolve()
    if str(full).startswith(str(peripheral)):
        return True
    if str(full).startswith(str(templates)):
        parts = [p for p in rel.split("/") if p]
        # templates/{template_id}/template.yaml or templates/{template_id}/blocks/...
        return (
            len(parts) == 3
            and parts[0] == "templates"
            and parts[2] == "template.yaml"
        ) or (
            len(parts) >= 4
            and parts[0] == "templates"
            and parts[2] == "blocks"
        )
    return False


def _validate_read_path(relative_path: str) -> None:
    rel = relative_path.strip().lstrip("/")
    if ".." in rel.split("/"):
        raise ValueError("Invalid path")
    full = (KNOWLEDGE_ROOT / rel).resolve()
    root = KNOWLEDGE_ROOT.resolve()
    if not str(full).startswith(str(root)):
        raise ValueError("Path escapes knowledge root")
    if not _is_allowed_knowledge_path(rel, full):
        raise ValueError("Path must be under peripheral/, templates/{template_id}/template.yaml, or templates/{template_id}/blocks/")


@tool(
    name="list_templates",
    description=(
        "List available proposal templates and their MDM catalog filters. "
        "Use when the user has not clearly chosen a proposal type, or asks what "
        "proposal types are supported. Do not use for service/package lookup — "
        "use list_mdm_packages / search_mdm_services instead. "
        "Read-only: may run in parallel with load_skill or MDM catalog tools."
    ),
)
def list_templates() -> dict[str, Any]:
    templates = load_templates()
    return {
        "templates": [
            {
                "template_id": row.get("template_id"),
                "display_name": row.get("display_name"),
                "catalog_filter": row.get("catalog_filter"),
            }
            for row in templates
        ]
    }


@tool(
    name="read_knowledge",
    description=(
        "Read text from knowledge/: peripheral/ (markdown, CSV, etc.) or "
        "templates/{template_id}/ (template.yaml, blocks/*.md). "
        "Use template.yaml to understand draft section ids/kinds/editability/derivations; "
        "use blocks/peripheral files for reusable proposal content. "
        "SKU/package pricing comes from Postgres MCP, not this tool."
    ),
)
def read_knowledge(
    path: Annotated[
        str,
        (
            "Relative path under knowledge/, e.g. "
            "templates/au-advisory/template.yaml, "
            "templates/harneys-bvi/blocks/terms-bvi.md, "
            "peripheral/required-docs/harneys/Individual KYC Requirements.md"
        ),
    ],
) -> dict[str, Any]:
    try:
        _validate_read_path(path)
        content = read_knowledge_file(path)
        return {"path": path, "content": content}
    except (OSError, ValueError) as exc:
        return {"path": path, "error": str(exc)}


@tool(
    name="initialize_proposal_draft",
    description=(
        "Create or reset the editable proposal draft from a chosen template. "
        "Use once after the template is known, or when the user explicitly switches "
        "template. This materializes template sections and preserves existing client "
        "facts when possible. Do not use for normal edits to an existing draft."
    ),
)
def initialize_proposal_draft(
    template_id: Annotated[str, "Proposal template_id, e.g. au-advisory."],
) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None:
        return {"status": "error", "error": "Proposal context unavailable for this run."}
    client = (ctx.draft or {}).get("facts", {}).get("client") or {}
    try:
        ctx.draft = materialize_draft(
            template_id=template_id,
            client=copy.deepcopy(client),
        )
        ctx.mark_draft_dirty()
        preview = build_draft_preview(ctx.draft)
        return {
            "status": "ok",
            "draft": copy.deepcopy(ctx.draft),
            "preview_status": preview.get("status"),
        }
    except Exception as exc:
        logger.exception("initialize_proposal_draft failed")
        return {"status": "error", "error": str(exc) or type(exc).__name__}


@tool(
    name="get_proposal_draft",
    description=(
        "Read the editable proposal draft that renders the right-hand Proposal Preview. "
        "Use before patching when you need exact section/table/row indexes or ids, and "
        "after draft write tools as the Reply gate truth source when verifying user intent "
        "before replying. Panel labels like 2.2 are render-time only (not stored in draft); locate the "
        "underlying draft row/field via get_proposal_draft and proposal-composer skill "
        "preview-vs-draft principles before patch. "
        "Omit path for the full draft; pass a JSON Pointer for a subtree. "
        "Read-only: may run in parallel with MCP catalog queries."
    ),
)
def get_proposal_draft(
    path: Annotated[str | None, "Optional JSON Pointer, e.g. /document/sections."] = None,
) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None:
        return {"status": "error", "error": "Proposal context unavailable for this run."}
    if ctx.draft is None:
        return {"status": "empty", "draft": None}
    if path:
        try:
            value = _resolve_pointer(ctx.draft, path)
        except Exception as exc:
            return {"status": "error", "path": path, "error": str(exc)}
        return {"status": "ok", "path": path, "value": copy.deepcopy(value)}
    return {"status": "ok", "draft": copy.deepcopy(ctx.draft)}


@tool(
    name="patch_proposal_draft",
    description=(
        "Apply RFC 6902 JSON Patch to existing proposal draft nodes. Use for visible "
        "display edits: client facts, section content, package brief content "
        "(/sections/{fee_index}/tables/{t}/brief/content), table titles, fee row "
        "display.preview_primary, display.amount_display (simple layout), "
        "display.frequency_columns_display / display.total_display (frequency layout), "
        "display.footnotes_display, row/table ordering, or derived_section configuration. "
        "fee_row.source is immutable — use add_package/add_services to materialize MDM rows "
        "and remove_fee_rows_from_proposal_draft to delete by SKU. "
        "If adding an MDM package or service, use add_package_to_proposal_draft/"
        "add_services_to_proposal_draft instead so catalog fields materialize correctly. "
        "JSON Patch replace requires the target path to already exist; use add for new fields."
    ),
)
def patch_proposal_draft(
    patch: Annotated[
        list[dict[str, Any]],
        "RFC 6902 JSON Patch array targeting proposal_draft paths. Read draft first if indexes are unknown.",
    ]
) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None:
        return {"status": "error", "error": "Proposal context unavailable for this run."}
    if ctx.draft is None:
        return {"status": "error", "error": "Proposal draft is not initialized."}
    try:
        ctx.draft = patch_draft(ctx.draft, patch)
        if any(
            str(op.get("path") or "").startswith("/facts/client")
            for op in patch
            if isinstance(op, dict)
        ):
            from app.proposal.placeholders import sync_draft_template_placeholders

            ctx.draft = sync_draft_template_placeholders(ctx.draft)
        ctx.mark_draft_dirty()
        return {"status": "ok", "patched": True, "draft": copy.deepcopy(ctx.draft)}
    except DraftPatchError as exc:
        return {"status": "error", "http_status": 422, "error": exc.message}
    except Exception as exc:
        logger.exception("patch_proposal_draft failed")
        return {"status": "error", "error": str(exc) or type(exc).__name__}


@tool(
    name="add_package_to_proposal_draft",
    description=(
        "Materialize a confirmed MDM package into the draft fee section. Pass package_id "
        "(or a package object with package_id); the tool loads all ACTIVE catalog services "
        "server-side — do not pass a partial services list. Re-adding the same package "
        "merges any missing SKUs into the existing table. "
        "Do not use for renaming/editing an existing package table; patch the draft. "
        "Mutates draft: call sequentially; do not parallelize with other draft write tools. "
        "Multiple packages: add one at a time in order."
    ),
)
def add_package_to_proposal_draft(
    package_id: Annotated[
        str | None,
        "MDM package_id, e.g. PKG001. Required unless package includes package_id.",
    ] = None,
    package: Annotated[
        Any | None,
        "Optional MDM package row (package_id, package_name). Ignored when package_id is set.",
    ] = None,
    services: Annotated[
        Any | None,
        "Deprecated — ignored. Services are always loaded from MDM catalog server-side.",
    ] = None,
) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None:
        return {"status": "error", "error": "Proposal context unavailable for this run."}
    if ctx.draft is None:
        return {"status": "error", "error": "Proposal draft is not initialized."}
    try:
        package_row = _coerce_object(package, "package") if package is not None else {}
        resolved_package_id = (package_id or package_row.get("package_id") or "").strip()
        if not resolved_package_id:
            raise ValueError("package_id is required")

        scope = resolve_catalog_scope()
        catalog = run_catalog_query(
            lambda session: get_package_services(session, scope, resolved_package_id)
        )
        package_row = catalog["package"]
        service_rows = catalog.get("services") or []
        if not service_rows:
            return {
                "status": "error",
                "error": f"No ACTIVE services found for package {resolved_package_id} in catalog scope.",
                "linked_sku_count": catalog.get("linked_sku_count", 0),
                "missing_skus": catalog.get("missing_skus") or [],
                "warnings": catalog.get("warnings") or [],
            }

        before_skus: set[str] = set()
        fee_section = next(
            (
                section
                for section in (ctx.draft.get("document") or {}).get("sections") or []
                if isinstance(section, dict) and section.get("kind") == "fee_section"
            ),
            None,
        )
        if isinstance(fee_section, dict):
            for table in fee_section.get("tables") or []:
                if not isinstance(table, dict):
                    continue
                if str((table.get("source") or {}).get("package_id") or "").strip() != resolved_package_id:
                    continue
                for row in table.get("rows") or []:
                    if isinstance(row, dict):
                        sku = str((row.get("source") or {}).get("sku") or "").strip()
                        if sku:
                            before_skus.add(sku)

        ctx.draft = add_package_to_draft(ctx.draft, package_row, service_rows)
        ctx.mark_draft_dirty()

        after_skus: set[str] = set()
        fee_section = next(
            (
                section
                for section in (ctx.draft.get("document") or {}).get("sections") or []
                if isinstance(section, dict) and section.get("kind") == "fee_section"
            ),
            None,
        )
        if isinstance(fee_section, dict):
            for table in fee_section.get("tables") or []:
                if not isinstance(table, dict):
                    continue
                if str((table.get("source") or {}).get("package_id") or "").strip() != resolved_package_id:
                    continue
                for row in table.get("rows") or []:
                    if isinstance(row, dict):
                        sku = str((row.get("source") or {}).get("sku") or "").strip()
                        if sku:
                            after_skus.add(sku)

        return {
            "status": "ok",
            "package_id": resolved_package_id,
            "catalog_service_count": len(service_rows),
            "linked_sku_count": catalog.get("linked_sku_count", len(service_rows)),
            "skus_in_draft": sorted(after_skus),
            "services_added": len(after_skus - before_skus),
            "missing_skus": catalog.get("missing_skus") or [],
            "warnings": catalog.get("warnings") or [],
            "draft": copy.deepcopy(ctx.draft),
        }
    except Exception as exc:
        logger.exception("add_package_to_proposal_draft failed")
        return {"status": "error", "error": str(exc) or type(exc).__name__}


@tool(
    name="add_services_to_proposal_draft",
    description=(
        "Materialize one or more confirmed MDM services/SKUs into the draft fee section. "
        "Pass services as an array of row objects from search_mdm_services (or equivalent "
        "catalog query), with pricing_type, price_amount, and fee_raw. "
        "A single service is represented as a one-item array. This tool does not query MDM. "
        "Do not use for editing display fields on rows already in the draft; patch display.* "
        "instead, or remove_fee_rows_from_proposal_draft to delete rows by SKU. "
        "Mutates draft: one call with all services in the array; do not parallelize multiple calls."
    ),
)
def add_services_to_proposal_draft(
    services: Annotated[Any, "Array of MDM service row objects, each including sku, pricing fields, and display fields."],
    table_id: Annotated[str | None, "Optional fee table id. Existing table is reused; otherwise a new table is created."] = None,
    table_title: Annotated[str, "Title used only when a new fee table is created."] = "Additional services",
) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None:
        return {"status": "error", "error": "Proposal context unavailable for this run."}
    if ctx.draft is None:
        return {"status": "error", "error": "Proposal draft is not initialized."}
    try:
        service_rows = _coerce_object_list(services, "services")
        ctx.draft = add_services_to_draft(ctx.draft, service_rows, table_id=table_id, table_title=table_title)
        ctx.mark_draft_dirty()
        return {"status": "ok", "draft": copy.deepcopy(ctx.draft)}
    except Exception as exc:
        logger.exception("add_services_to_proposal_draft failed")
        return {"status": "error", "error": str(exc) or type(exc).__name__}


@tool(
    name="remove_fee_rows_from_proposal_draft",
    description=(
        "Remove fee rows from the draft by source SKU. Use when the user asks to drop "
        "specific services from the proposal. Match rows by display.preview_primary for "
        "user-facing language, but pass source SKUs to this tool. "
        "Mutates draft: do not parallelize with other draft write tools."
    ),
)
def remove_fee_rows_from_proposal_draft(
    skus: Annotated[list[str], "SKUs to remove (source.sku values), e.g. ['TA01', 'CSS23']."],
) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None:
        return {"status": "error", "error": "Proposal context unavailable for this run."}
    if ctx.draft is None:
        return {"status": "error", "error": "Proposal draft is not initialized."}
    try:
        ctx.draft = remove_fee_rows_by_sku(ctx.draft, skus)
        ctx.mark_draft_dirty()
        return {"status": "ok", "removed_skus": skus, "draft": copy.deepcopy(ctx.draft)}
    except Exception as exc:
        logger.exception("remove_fee_rows_from_proposal_draft failed")
        return {"status": "error", "error": str(exc) or type(exc).__name__}


@tool(
    name="enable_proposal_draft_section",
    description=(
        "Enable or disable an optional draft section by section id (e.g. payment_options, "
        "credentials, appendices). Use only for sections already defined in the template. "
        "For kind derived_section, enabling shows the platform default derivation only; "
        "alternate variants require a follow-up patch_proposal_draft on that section's "
        "config fields (read get_proposal_draft for field names). Do not use to create "
        "new arbitrary sections."
    ),
)
def enable_proposal_draft_section(
    section_id: Annotated[str, "Draft section id, e.g. payment_options."],
    enabled: Annotated[bool, "Whether the section should be enabled."] = True,
) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None:
        return {"status": "error", "error": "Proposal context unavailable for this run."}
    if ctx.draft is None:
        return {"status": "error", "error": "Proposal draft is not initialized."}
    try:
        ctx.draft = enable_draft_section(ctx.draft, section_id, enabled=enabled)
        ctx.mark_draft_dirty()
        return {"status": "ok", "draft": copy.deepcopy(ctx.draft)}
    except DraftPatchError as exc:
        return {"status": "error", "http_status": 422, "error": exc.message}
    except Exception as exc:
        logger.exception("enable_proposal_draft_section failed")
        return {"status": "error", "error": str(exc) or type(exc).__name__}


def _artifact_download_url(chat_id, artifact_id: str) -> str:
    return f"/api/v1/chats/{chat_id}/artifacts/{artifact_id}"


def _build_artifact_spec(
    *,
    kind: ArtifactKind,
    title: str,
    content: str,
    filename: str,
    chat_id,
    persist: bool,
) -> ArtifactSpec:
    artifact_id = new_artifact_id()
    download_url = None
    if persist and chat_id is not None:
        save_markdown(chat_id, artifact_id, content, filename=filename)
        download_url = _artifact_download_url(chat_id, artifact_id)
    preview_truncated = len(content) > _PREVIEW_CHAR_LIMIT
    return ArtifactSpec(
        kind=kind,
        title=title,
        content=content,
        filename=filename,
        artifact_id=artifact_id,
        download_url=download_url,
        preview_truncated=preview_truncated,
    )


def _queue_artifact(spec: ArtifactSpec) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None:
        return {"status": "error", "message": "Proposal context unavailable for this run."}
    queued = ctx.queue_artifact(spec)
    payload = spec.model_dump(mode="json")
    payload["status"] = "queued" if queued else "deduplicated"
    payload["queued"] = queued
    return payload


@tool(
    name="render_preview",
    description=(
        "Return a lightweight status for the current proposal draft preview. The UI already "
        "auto-renders after draft write tools, so call this only when you need to confirm "
        "preview/readiness status for your response. Do not call repeatedly after every patch."
    ),
)
def render_preview(
    draft: Annotated[bool, "Deprecated compatibility flag; draft preview is always used."] = False,
) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None:
        return {"status": "error", "message": "Proposal context unavailable for this run."}

    if ctx.draft is None:
        return {
            "status": "empty",
            "message": "Proposal draft is not initialized.",
            "missing_required": [],
        }

    preview = build_draft_preview(ctx.draft)
    return {
        "status": preview.get("status") or "ok",
        "message": "Live proposal panel updates automatically after draft changes.",
        "title": preview.get("title"),
        "state_fingerprint": preview.get("state_fingerprint"),
        "completeness": preview.get("completeness"),
        "missing_required": (preview.get("completeness") or {}).get("missing_required") or [],
    }


@tool(
    name="generate_document",
    description=(
        "Create a downloadable proposal markdown file from the current draft. Use only when "
        "the user asks to export/download/send/finalize a proposal. The live Proposal panel "
        "already shows the draft, so do not use this for ordinary preview. If blocked for "
        "missing required content, ask for the missing business information or use force only "
        "when the user explicitly accepts an incomplete file."
    ),
)
def generate_document(
    force: Annotated[bool, "If true, generate even when the draft is not ready_to_generate. Use only with user consent."] = False,
) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None:
        return {"status": "error", "message": "Proposal context unavailable for this run."}

    if ctx.draft is None:
        return {"status": "empty", "message": "Proposal draft is not initialized."}

    preview = build_draft_preview(ctx.draft)
    completeness = preview.get("completeness") or {}
    if not force and not completeness.get("ready_to_generate"):
        return {
            "status": "blocked",
            "message": "Proposal draft is not ready to generate.",
            "missing_required": completeness.get("missing_required") or [],
        }
    content = render_draft_markdown(ctx.draft)
    title = str((ctx.draft.get("meta") or {}).get("title") or "Proposal")
    spec = _build_artifact_spec(
        kind="proposal_document",
        title=title,
        content=content,
        filename=preview.get("filename") or "proposal.md",
        chat_id=ctx.chat_id,
        persist=True,
    )
    ctx.mark_draft_dirty()
    payload = _queue_artifact(spec)
    payload["download_url"] = spec.download_url
    payload["filename"] = spec.filename
    return payload


@tool(
    name="generate_word_document",
    description=(
        "Create a downloadable Word (.docx) proposal from the current draft using the "
        "template's Word export file. Use when the user asks to export/download/send a "
        "Word document or .docx proposal. Requires a Word template configured for the "
        "proposal template. Same readiness rules as generate_document."
    ),
)
def generate_word_document(
    force: Annotated[bool, "If true, generate even when the draft is not ready_to_generate. Use only with user consent."] = False,
) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None:
        return {"status": "error", "message": "Proposal context unavailable for this run."}

    if ctx.draft is None:
        return {"status": "empty", "message": "Proposal draft is not initialized."}

    try:
        result = generate_proposal_docx(
            ctx.draft,
            chat_id=ctx.chat_id,
            force=force,
            persist=True,
        )
    except ProposalExportError as exc:
        payload: dict[str, Any] = {
            "status": exc.code if exc.code in {"blocked", "empty", "no_word_template"} else "error",
            "message": exc.message,
        }
        if exc.code == "blocked":
            preview = build_draft_preview(ctx.draft)
            payload["missing_required"] = (preview.get("completeness") or {}).get("missing_required") or []
        return payload

    spec = ArtifactSpec(
        kind="proposal_word",
        title=result["title"],
        format="docx",
        content="",
        filename=result["filename"],
        artifact_id=result["artifact_id"],
        download_url=result["download_url"],
        preview_truncated=False,
    )
    ctx.mark_draft_dirty()
    payload = _queue_artifact(spec)
    payload["download_url"] = spec.download_url
    payload["filename"] = spec.filename
    payload["format"] = "docx"
    return payload

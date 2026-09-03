"""Fee row source/display model — materialize, resolve, and effective pricing."""

from __future__ import annotations

import copy
import re
from typing import Any

from app.proposal.fee_table import format_money, row_frequency_columns, row_total_annualized
from app.proposal.footnotes import normalize_footnote
from app.proposal.pricing_rules import coerce_price_amount, fee_table_amount_display, normalize_pricing_type

_STANDARD_OFFER_RE = re.compile(r"\s*\((?:standard offer|standard fee|pricing)[^)]+\)\s*$", re.I)
_AMOUNT_PARSE_RE = re.compile(r"[\d,]+\.?\d*")


def _clean_service_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    cleaned = _STANDARD_OFFER_RE.sub("", raw).strip()
    return cleaned or raw


def _normalize_department(value: Any) -> str:
    dept = str(value or "").strip()
    if not dept or dept.lower() == "nan":
        return "Services"
    return dept


def parse_amount_display(text: str | None) -> float | None:
    if not text:
        return None
    match = _AMOUNT_PARSE_RE.search(str(text).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _is_literal_display_override(patched: str, canonical: str) -> bool:
    """Keep patched display text verbatim when it adds wording beyond auto-generated price."""
    text = str(patched or "").strip()
    baseline = str(canonical or "").strip()
    if not text:
        return False
    if text == baseline:
        return False
    parsed_text = parse_amount_display(text)
    parsed_base = parse_amount_display(baseline)
    if parsed_text is not None and parsed_base is not None and parsed_text == parsed_base:
        return True
    if parsed_text is not None and parsed_base is not None:
        return False
    return True


def build_mdm_source(
    service: dict[str, Any],
    *,
    package_id: str | None = None,
    jurisdiction: str | None = None,
    bu: str | None = None,
) -> dict[str, Any]:
    sku = str(service["sku"])
    source: dict[str, Any] = {
        "type": "mdm_service",
        "sku": sku,
        "service_name": _clean_service_name(service.get("service_name")) or sku,
        "description": str(service.get("description") or "").strip() or None,
        "scope_of_work": str(service.get("scope_of_work") or "").strip() or None,
        "department_team": _normalize_department(service.get("department_team")),
        "billing_frequency": str(service.get("billing_frequency") or "ONE_TIME").strip(),
        "recurring": str(service.get("recurring") or "ONE_OFF").strip(),
        "status": "ACTIVE",
        "pricing_type": normalize_pricing_type(service.get("pricing_type")),
        "price_currency": str(service.get("price_currency") or "").strip() or None,
        "price_amount": coerce_price_amount(service.get("price_amount")),
        "fee_raw": str(service.get("fee_raw") or "").strip() or None,
        "footnotes": normalize_footnote(service.get("footnotes")),
    }
    if package_id:
        source["package_id"] = package_id
    if jurisdiction:
        source["jurisdiction"] = jurisdiction
    if bu:
        source["bu"] = bu
    semantic = str(service.get("sku_semantic_for_ai") or "").strip()
    if semantic:
        source["sku_semantic_for_ai"] = semantic
    return source


def build_custom_source(*, sku: str) -> dict[str, Any]:
    return {"type": "custom_service", "sku": sku}


def _price_object_from_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "amount": coerce_price_amount(source.get("price_amount")),
        "fee_raw": source.get("fee_raw"),
        "currency": source.get("price_currency") or "",
        "frequency": source.get("billing_frequency") or "ONE_TIME",
        "recurring": source.get("recurring") or "ONE_OFF",
        "pricing_type": normalize_pricing_type(source.get("pricing_type")),
    }


def _preview_primary(source: dict[str, Any], layout: dict[str, Any]) -> str:
    from app.proposal.fee_table import service_column_flags

    columns = service_column_flags(layout)
    service_name = str(source.get("service_name") or source.get("sku") or "").strip()
    description = str(source.get("description") or "").strip()
    sku = str(source.get("sku") or "").strip()

    if columns.get("service_name") and service_name:
        return service_name
    if columns.get("description") and description:
        return description
    return sku or service_name or description


def _format_frequency_column_display(amount: float | None, currency: str) -> str:
    if amount is None:
        return ""
    return format_money(amount, currency, include_currency=bool(currency)).strip()


def _recurring_suffix(billing_frequency: str) -> str:
    freq = str(billing_frequency or "ONE_TIME").upper()
    labels = {
        "MONTHLY": "Monthly",
        "QUARTERLY": "Quarterly",
        "ANNUALLY": "Annual",
    }
    if freq in labels:
        return labels[freq]
    raw = str(billing_frequency or "").strip()
    if not raw or freq == "ONE_TIME":
        return ""
    return raw


def _append_billing_frequency_to_amount(
    amount_text: str,
    billing_frequency: str,
    *,
    layout: dict[str, Any],
) -> str:
    text = str(amount_text or "").strip()
    if not text:
        return text
    if not layout.get("show_billing_frequency"):
        return text
    if str(layout.get("table_style") or "simple").strip().lower() != "simple":
        return text
    suffix = _recurring_suffix(billing_frequency)
    if not suffix or suffix.lower() in text.lower():
        return text
    return f"{text} {suffix}"


def _build_once_off_recurring_displays(price: dict[str, Any], *, currency: str) -> tuple[str, str]:
    """Split fee text into one-off vs recurring display strings (layout-agnostic canonical)."""
    freq = str(price.get("frequency") or "ONE_TIME").upper()
    amount_text = fee_table_amount_display(price, format_money=format_money) or ""
    if freq == "ONE_TIME":
        return amount_text, ""
    suffix = _recurring_suffix(freq)
    if amount_text and suffix and suffix.lower() not in amount_text.lower():
        recurring = f"{amount_text} {suffix}".strip()
    else:
        recurring = amount_text
    return "", recurring


def _build_canonical_display_fields(
    source: dict[str, Any],
    *,
    layout: dict[str, Any],
) -> dict[str, Any]:
    """Layout-agnostic display snapshot — all table styles read from this."""
    from app.proposal.fee_table import service_column_flags

    columns = service_column_flags(layout)
    price = _price_object_from_source(source)
    currency = str(price.get("currency") or "")

    display: dict[str, Any] = {
        "preview_primary": _preview_primary(source, layout),
    }

    footnotes = normalize_footnote(source.get("footnotes"))
    if footnotes:
        display["footnotes_display"] = footnotes

    sow = str(source.get("scope_of_work") or "").strip()
    if sow and (columns.get("scope_of_work") or sow):
        display["scope_of_work_display"] = sow

    amount = price.get("amount")
    freq_cols = row_frequency_columns(
        {"amount": amount, "billing_frequency": price.get("frequency")}
    )
    display["frequency_columns_display"] = {
        key: _format_frequency_column_display(freq_cols.get(key), currency)
        for key in ("monthly", "quarterly", "annual", "once_off")
    }
    fee_raw = fee_table_amount_display(price, format_money=format_money)
    if fee_raw and normalize_pricing_type(price.get("pricing_type")) != "FIXED":
        active = str(price.get("frequency") or "ONE_TIME").upper()
        col_map = {
            "MONTHLY": "monthly",
            "QUARTERLY": "quarterly",
            "ANNUALLY": "annual",
        }
        active_key = col_map.get(active, "once_off")
        display["frequency_columns_display"][active_key] = fee_raw

    total = row_total_annualized(freq_cols) if amount is not None else None
    display["total_display"] = (
        format_money(total, currency, include_currency=bool(currency)).strip()
        if total is not None
        else ""
    )

    amount_text = fee_table_amount_display(price, format_money=format_money)
    if amount_text:
        display["amount_display"] = _append_billing_frequency_to_amount(
            amount_text,
            str(price.get("frequency") or "ONE_TIME"),
            layout=layout,
        )

    once_off, recurring = _build_once_off_recurring_displays(price, currency=currency)
    display["once_off_display"] = once_off
    display["recurring_display"] = recurring

    return display


def resolve_fee_row(source: dict[str, Any], *, layout: dict[str, Any]) -> dict[str, Any]:
    return _build_canonical_display_fields(source, layout=layout)


def resolve_fee_row_display(row: dict[str, Any], *, layout: dict[str, Any]) -> dict[str, Any]:
    source = row.get("source")
    if not isinstance(source, dict):
        raise ValueError("fee_row.source must be an object")
    display = copy.deepcopy(row.get("display") or {})
    if str(source.get("type") or "") == "custom_service":
        return _normalize_custom_display(display, layout=layout)
    if display:
        return _apply_display_overrides(source, display, layout=layout)
    return resolve_fee_row(source, layout=layout)


def _apply_display_overrides(
    source: dict[str, Any],
    display: dict[str, Any],
    *,
    layout: dict[str, Any],
) -> dict[str, Any]:
    """Merge canonical fields with explicit display edits; recompute price-derived columns."""
    base = _build_canonical_display_fields(source, layout=layout)
    merged = {**base, **display}
    price = _price_object_from_source(source)
    currency = str(price.get("currency") or "")

    if "once_off_display" in display:
        patched_text = str(display.get("once_off_display") or "").strip()
        canonical_text = str(base.get("once_off_display") or "").strip()
        if _is_literal_display_override(patched_text, canonical_text):
            merged["once_off_display"] = patched_text
        else:
            parsed = parse_amount_display(patched_text)
            if parsed is not None:
                price = {**price, "amount": parsed, "frequency": "ONE_TIME"}
                merged["once_off_display"] = fee_table_amount_display(price, format_money=format_money) or patched_text
            else:
                merged["once_off_display"] = patched_text
        merged["recurring_display"] = str(display.get("recurring_display") or merged.get("recurring_display") or "")

    if "recurring_display" in display and "once_off_display" not in display:
        patched_text = str(display.get("recurring_display") or "").strip()
        canonical_text = str(base.get("recurring_display") or "").strip()
        if _is_literal_display_override(patched_text, canonical_text):
            merged["recurring_display"] = patched_text
        else:
            parsed = parse_amount_display(patched_text)
            if parsed is not None:
                price = {**price, "amount": parsed}
                merged["recurring_display"] = patched_text or merged.get("recurring_display") or ""
            else:
                merged["recurring_display"] = patched_text

    amount_price_updated = False
    if "amount_display" in display:
        patched_text = str(display.get("amount_display") or "").strip()
        canonical_text = str(base.get("amount_display") or "").strip()
        if _is_literal_display_override(patched_text, canonical_text):
            merged["amount_display"] = patched_text
        else:
            parsed = parse_amount_display(patched_text)
            if parsed is not None:
                price = {**price, "amount": parsed}
            formatted = fee_table_amount_display(price, format_money=format_money) or patched_text
            merged["amount_display"] = _append_billing_frequency_to_amount(
                formatted,
                str(price.get("frequency") or "ONE_TIME"),
                layout=layout,
            )
            amount_price_updated = True

    if isinstance(display.get("frequency_columns_display"), dict):
        freq_patch = display["frequency_columns_display"]
        active = str(price.get("frequency") or "ONE_TIME").upper()
        col_map = {
            "MONTHLY": "monthly",
            "QUARTERLY": "quarterly",
            "ANNUALLY": "annual",
            "ONE_TIME": "once_off",
        }
        active_key = col_map.get(active, "once_off")
        base_freq = base.get("frequency_columns_display") or {}
        for key in (active_key, "once_off", "annual", "quarterly", "monthly"):
            if key not in freq_patch:
                continue
            patched_text = str(freq_patch.get(key) or "").strip()
            canonical_text = str((base_freq.get(key) if isinstance(base_freq, dict) else "") or "").strip()
            if _is_literal_display_override(patched_text, canonical_text):
                continue
            parsed = parse_amount_display(patched_text)
            if parsed is not None:
                price = {**price, "amount": parsed}
                if key == "once_off":
                    price = {**price, "frequency": "ONE_TIME"}
                amount_price_updated = True
                break

    amount = price.get("amount")
    if amount is not None and (
        amount_price_updated
        or (
            "once_off_display" in display
            and not _is_literal_display_override(
                str(display.get("once_off_display") or "").strip(),
                str(base.get("once_off_display") or "").strip(),
            )
        )
        or (
            "recurring_display" in display
            and "once_off_display" not in display
            and not _is_literal_display_override(
                str(display.get("recurring_display") or "").strip(),
                str(base.get("recurring_display") or "").strip(),
            )
        )
        or "frequency_columns_display" in display
    ):
        freq_cols = row_frequency_columns(
            {"amount": amount, "billing_frequency": price.get("frequency")}
        )
        if "frequency_columns_display" in display:
            merged["frequency_columns_display"] = {
                **(merged.get("frequency_columns_display") or {}),
                **display["frequency_columns_display"],
            }
        else:
            merged["frequency_columns_display"] = {
                key: _format_frequency_column_display(freq_cols.get(key), currency)
                for key in ("monthly", "quarterly", "annual", "once_off")
            }
        total = row_total_annualized(freq_cols)
        if "total_display" not in display:
            merged["total_display"] = format_money(total, currency, include_currency=bool(currency)).strip()
        once_off, recurring = _build_once_off_recurring_displays(price, currency=currency)
        if "once_off_display" not in display:
            merged["once_off_display"] = once_off
        if "recurring_display" not in display:
            merged["recurring_display"] = recurring

    if not str(merged.get("preview_primary") or "").strip():
        merged["preview_primary"] = _preview_primary(source, layout)

    return merged


def _normalize_custom_display(display: dict[str, Any], *, layout: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(display)
    preview = str(normalized.get("preview_primary") or "").strip()
    if not preview:
        raise ValueError("custom fee_row.display.preview_primary is required")
    amount_text = str(normalized.get("amount_display") or "").strip()
    once_off_text = str(normalized.get("once_off_display") or "").strip()
    recurring_text = str(normalized.get("recurring_display") or "").strip()
    currency = ""
    for probe in (amount_text, once_off_text, recurring_text):
        if probe.upper().startswith("AUD"):
            currency = "AUD"
            break
        if probe.upper().startswith("USD"):
            currency = "USD"
            break

    if once_off_text or recurring_text:
        if once_off_text and not recurring_text:
            normalized.setdefault("once_off_display", once_off_text)
        elif recurring_text and not once_off_text:
            normalized.setdefault("recurring_display", recurring_text)
    elif amount_text:
        parsed = parse_amount_display(amount_text)
        price = {
            "amount": parsed,
            "fee_raw": None,
            "currency": currency,
            "frequency": "ONE_TIME",
            "pricing_type": "FIXED",
        }
        once_off, recurring = _build_once_off_recurring_displays(price, currency=currency)
        normalized.setdefault("once_off_display", once_off or amount_text)
        normalized.setdefault("recurring_display", recurring)

    table_style = str(layout.get("table_style") or "simple").strip().lower()
    if table_style == "frequency_columns":
        if "frequency_columns_display" not in normalized and amount_text:
            parsed = parse_amount_display(amount_text)
            cols = row_frequency_columns({"amount": parsed, "billing_frequency": "ONE_TIME"})
            normalized["frequency_columns_display"] = {
                key: _format_frequency_column_display(cols.get(key), currency)
                for key in ("monthly", "quarterly", "annual", "once_off")
            }
            if parsed is not None:
                normalized["total_display"] = format_money(parsed, currency, include_currency=bool(currency)).strip()
    elif amount_text:
        normalized["amount_display"] = _append_billing_frequency_to_amount(
            amount_text,
            "ONE_TIME",
            layout=layout,
        )
    return normalized


def materialize_mdm_fee_row(
    service: dict[str, Any],
    *,
    package_id: str | None,
    layout: dict[str, Any],
    jurisdiction: str | None = None,
    bu: str | None = None,
) -> dict[str, Any]:
    source = build_mdm_source(
        service,
        package_id=package_id,
        jurisdiction=jurisdiction,
        bu=bu,
    )
    display = resolve_fee_row(source, layout=layout)
    return {
        "id": f"fee_{source['sku']}",
        "kind": "fee_row",
        "source": source,
        "display": display,
    }


def materialize_custom_fee_row(
    *,
    sku: str,
    display: dict[str, Any],
    layout: dict[str, Any],
) -> dict[str, Any]:
    source = build_custom_source(sku=sku)
    normalized_display = _normalize_custom_display(display, layout=layout)
    return {
        "id": f"fee_{sku}",
        "kind": "fee_row",
        "source": source,
        "display": normalized_display,
    }


def row_sku(row: dict[str, Any]) -> str:
    source = row.get("source")
    if isinstance(source, dict) and source.get("sku"):
        return str(source["sku"]).strip()
    row_id = str(row.get("id") or "").strip()
    if row_id.startswith("fee_"):
        return row_id.removeprefix("fee_")
    return row_id


def row_department(row: dict[str, Any]) -> str:
    source = row.get("source")
    if isinstance(source, dict):
        return _normalize_department(source.get("department_team"))
    return "Services"


def row_footnote_text(row: dict[str, Any]) -> str | None:
    display = row.get("display")
    if isinstance(display, dict):
        text = normalize_footnote(display.get("footnotes_display"))
        if text:
            return text
    source = row.get("source")
    if isinstance(source, dict):
        return normalize_footnote(source.get("footnotes"))
    return None


def effective_pricing(row: dict[str, Any]) -> dict[str, Any]:
    source = row.get("source") if isinstance(row.get("source"), dict) else {}
    display = row.get("display") if isinstance(row.get("display"), dict) else {}
    source_type = str(source.get("type") or "")

    if source_type == "custom_service":
        amount = parse_amount_display(str(display.get("amount_display") or ""))
        if amount is None and isinstance(display.get("frequency_columns_display"), dict):
            for key in ("once_off", "annual", "quarterly", "monthly"):
                parsed = parse_amount_display(str(display["frequency_columns_display"].get(key) or ""))
                if parsed is not None:
                    amount = parsed
                    break
        billing_frequency = "ONE_TIME"
        currency = ""
        amount_text = str(display.get("amount_display") or display.get("total_display") or "")
        if "AUD" in amount_text.upper():
            currency = "AUD"
        elif "USD" in amount_text.upper():
            currency = "USD"
        converted = {
            "amount": amount,
            "billing_frequency": billing_frequency,
            "currency": currency,
            "pricing_type": "FIXED",
        }
        converted["frequency_columns"] = row_frequency_columns(converted)
        return converted

    price = _price_object_from_source(source)
    active = str(price.get("frequency") or "ONE_TIME").upper()
    col_map = {
        "MONTHLY": "monthly",
        "QUARTERLY": "quarterly",
        "ANNUALLY": "annual",
        "ONE_TIME": "once_off",
    }
    active_key = col_map.get(active, "once_off")
    if isinstance(display.get("frequency_columns_display"), dict):
        parsed = parse_amount_display(str(display["frequency_columns_display"].get(active_key) or ""))
        if parsed is not None:
            price["amount"] = parsed
    if display.get("once_off_display") and not isinstance(display.get("frequency_columns_display"), dict):
        parsed = parse_amount_display(str(display.get("once_off_display") or ""))
        if parsed is not None:
            price["amount"] = parsed
            price["frequency"] = "ONE_TIME"
    elif display.get("recurring_display") and not isinstance(display.get("frequency_columns_display"), dict):
        parsed = parse_amount_display(str(display.get("recurring_display") or ""))
        if parsed is not None:
            price["amount"] = parsed
    if "amount_display" in display and not isinstance(display.get("frequency_columns_display"), dict):
        parsed = parse_amount_display(str(display.get("amount_display") or ""))
        if parsed is not None:
            price["amount"] = parsed

    converted = {
        "amount": price.get("amount"),
        "billing_frequency": price.get("frequency") or "ONE_TIME",
        "currency": price.get("currency") or "",
        "pricing_type": price.get("pricing_type"),
        "amount_display": display.get("amount_display") or display.get("total_display"),
    }
    converted["frequency_columns"] = row_frequency_columns(converted)
    return converted


def render_row_dto(row: dict[str, Any]) -> dict[str, Any]:
    """Minimal row payload for preview render and footnote collection."""
    display = row.get("display") if isinstance(row.get("display"), dict) else {}
    pricing = effective_pricing(row)
    dto: dict[str, Any] = {
        "sku": row_sku(row),
        "department_team": row_department(row),
        "footnotes": row_footnote_text(row),
        "display": copy.deepcopy(display),
        "preview_primary": display.get("preview_primary"),
        "amount_display": display.get("amount_display") or display.get("total_display"),
        "amount": pricing.get("amount"),
        "currency": pricing.get("currency"),
        "billing_frequency": pricing.get("billing_frequency"),
        "pricing_type": pricing.get("pricing_type"),
        "frequency_columns": pricing.get("frequency_columns"),
    }
    if isinstance(display.get("frequency_columns_display"), dict):
        dto["frequency_columns_display"] = copy.deepcopy(display["frequency_columns_display"])
    if display.get("scope_of_work_display"):
        dto["scope_of_work_display"] = display.get("scope_of_work_display")
    if display.get("once_off_display") is not None:
        dto["once_off_display"] = display.get("once_off_display")
    if display.get("recurring_display") is not None:
        dto["recurring_display"] = display.get("recurring_display")
    return dto


def iter_fee_rows(draft: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    """Yield (section, table, row) for each fee_row in the draft."""
    document = draft.get("document") or {}
    sections = document.get("sections") if isinstance(document, dict) else []
    if not isinstance(sections, list):
        return []
    found: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for section in sections:
        if not isinstance(section, dict) or section.get("kind") != "fee_section":
            continue
        for table in section.get("tables") or []:
            if not isinstance(table, dict):
                continue
            for row in table.get("rows") or []:
                if isinstance(row, dict) and row.get("kind") == "fee_row":
                    found.append((section, table, row))
    return found


def remove_fee_rows_by_sku(draft: dict[str, Any], skus: list[str]) -> dict[str, Any]:
    targets = {str(sku).strip() for sku in skus if str(sku).strip()}
    if not targets:
        raise ValueError("skus are required")
    updated = copy.deepcopy(draft)
    removed = 0
    for section in (updated.get("document") or {}).get("sections") or []:
        if not isinstance(section, dict) or section.get("kind") != "fee_section":
            continue
        for table in section.get("tables") or []:
            if not isinstance(table, dict):
                continue
            rows = table.get("rows") or []
            kept = [row for row in rows if isinstance(row, dict) and row_sku(row) not in targets]
            removed += len(rows) - len(kept)
            table["rows"] = kept
    if removed == 0:
        raise ValueError(f"No fee rows matched skus: {', '.join(sorted(targets))}")
    return updated

DEFAULT_ADHOC_EXCLUDE_PATTERN = r"(?i)(?<![a-z-])ad[\s-]?hoc(?![a-z])"
DEFAULT_ADHOC_EXCLUDE_FIELDS = (
    "preview_primary",
    "scope_of_work_display",
    "service_name",
    "description",
    "scope_of_work",
)


def _exclude_field_text(row: dict[str, Any], field: str) -> str:
    display = row.get("display") if isinstance(row.get("display"), dict) else {}
    source = row.get("source") if isinstance(row.get("source"), dict) else {}
    if field == "preview_primary":
        return str(display.get("preview_primary") or "").strip()
    if field == "scope_of_work_display":
        return str(display.get("scope_of_work_display") or "").strip()
    if field in ("service_name", "description", "scope_of_work"):
        value = source.get(field)
        if value not in (None, ""):
            return str(value).strip()
        if field == "service_name":
            return str(display.get("preview_primary") or "").strip()
    return ""


def is_adhoc_fee_row(row: dict[str, Any], exclude_cfg: dict[str, Any] | None = None) -> bool:
    """True when row text matches template derivation.exclude adhoc pattern."""
    cfg = exclude_cfg or {}
    pattern = str(cfg.get("pattern") or DEFAULT_ADHOC_EXCLUDE_PATTERN)
    fields = cfg.get("fields") or list(DEFAULT_ADHOC_EXCLUDE_FIELDS)
    try:
        regex = re.compile(pattern)
    except re.error:
        regex = re.compile(DEFAULT_ADHOC_EXCLUDE_PATTERN)
    for field in fields:
        text = _exclude_field_text(row, str(field))
        if text and regex.search(text):
            return True
    return False


def first_invoice_row_amount(row: dict[str, Any], layout: dict[str, Any] | None) -> float | None:
    """First-invoice price from draft display fields (not source catalog amounts)."""
    layout = layout or {}
    style = str(layout.get("table_style") or "simple").strip().lower()
    display = row.get("display") if isinstance(row.get("display"), dict) else {}

    if style == "one_off_recurring":
        once_off = parse_amount_display(str(display.get("once_off_display") or ""))
        recurring = parse_amount_display(str(display.get("recurring_display") or ""))
        parts = [value for value in (once_off, recurring) if value is not None]
        if not parts:
            return None
        return float(sum(parts))

    if style == "frequency_columns":
        freq_cols = display.get("frequency_columns_display")
        if isinstance(freq_cols, dict):
            once_off = parse_amount_display(str(freq_cols.get("once_off") or ""))
            if once_off is not None:
                return once_off
            for key in ("monthly", "quarterly", "annual"):
                parsed = parse_amount_display(str(freq_cols.get(key) or ""))
                if parsed is not None:
                    return parsed
        amount = effective_pricing(row).get("amount")
        return float(amount) if amount is not None else None

    parsed = parse_amount_display(str(display.get("amount_display") or ""))
    if parsed is not None:
        return parsed
    amount = effective_pricing(row).get("amount")
    return float(amount) if amount is not None else None


def validate_fee_row_patches(patch: list[dict[str, Any]]) -> None:
    from app.proposal.draft import DraftPatchError

    for op in patch:
        if not isinstance(op, dict):
            continue
        path = str(op.get("path") or "")
        if "/source" in path and "/rows/" in path:
            raise DraftPatchError("fee_row.source is immutable; patch display fields instead.")

"""Live probes against DashScope (百炼 OpenAI-compatible)."""

from __future__ import annotations

import time
from typing import Any

from scripts.probe_file_api_phase0.fixtures import (
    PROBE_MD_SENTINEL,
    PROBE_PDF_SENTINEL,
    fileid_system_message,
    make_minimal_pdf,
    make_probe_markdown,
    openai_pdf_file_data_part,
)
from scripts.probe_file_api_phase0.http_client import OpenAICompatibleClient
from scripts.probe_file_api_phase0.report import ProbeReport, ProbeResult, ProbeStatus


async def _run_probe(
    report: ProbeReport,
    *,
    probe_id: str,
    label: str,
    coro_factory,
) -> Any | None:
    started = time.monotonic()
    try:
        value = await coro_factory()
        duration_ms = int((time.monotonic() - started) * 1000)
        report.add(
            ProbeResult(
                id=probe_id,
                label=label,
                status=ProbeStatus.PASS,
                detail="ok",
                evidence=value if isinstance(value, dict) else {"value": value},
                duration_ms=duration_ms,
            )
        )
        return value
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        report.add(
            ProbeResult(
                id=probe_id,
                label=label,
                status=ProbeStatus.FAIL,
                detail=str(exc),
                duration_ms=duration_ms,
            )
        )
        return None


async def run_dashscope_probes(
    client: OpenAICompatibleClient,
    report: ProbeReport,
    *,
    models: dict[str, str],
) -> dict[str, str | None]:
    """Run DashScope probes; returns uploaded file ids for cross-reference."""
    file_ids: dict[str, str | None] = {"md": None, "pdf": None}

    async def upload_md() -> dict[str, Any]:
        payload = await client.upload_file(
            filename="probe.md",
            data=make_probe_markdown(long=True),
            mime_type="text/markdown",
            purpose="file-extract",
        )
        file_ids["md"] = str(payload["id"])
        return {"file_id": payload["id"], "status": payload.get("status")}

    await _run_probe(
        report,
        probe_id="dashscope.upload_md_fileextract",
        label="DashScope upload MD (purpose=file-extract)",
        coro_factory=upload_md,
    )

    async def poll_md() -> dict[str, Any]:
        md_id = file_ids["md"]
        if not md_id:
            raise RuntimeError("skipped: md upload failed")
        final = await client.wait_file_processed(md_id)
        return {"file_id": md_id, "status": final.get("status")}

    await _run_probe(
        report,
        probe_id="dashscope.poll_md_processed",
        label="DashScope poll MD until processed",
        coro_factory=poll_md,
    )

    async def upload_pdf() -> dict[str, Any]:
        payload = await client.upload_file(
            filename="probe.pdf",
            data=make_minimal_pdf(),
            mime_type="application/pdf",
            purpose="file-extract",
        )
        file_ids["pdf"] = str(payload["id"])
        return {"file_id": payload["id"], "status": payload.get("status")}

    await _run_probe(
        report,
        probe_id="dashscope.upload_pdf_fileextract",
        label="DashScope upload PDF (purpose=file-extract)",
        coro_factory=upload_pdf,
    )

    async def poll_pdf() -> dict[str, Any]:
        pdf_id = file_ids["pdf"]
        if not pdf_id:
            raise RuntimeError("skipped: pdf upload failed")
        final = await client.wait_file_processed(pdf_id)
        return {"file_id": pdf_id, "status": final.get("status")}

    await _run_probe(
        report,
        probe_id="dashscope.poll_pdf_processed",
        label="DashScope poll PDF until processed",
        coro_factory=poll_pdf,
    )

    # --- fileid:// chat probes (long MD — official file-extract consumer is qwen-long) ---
    for model_key, model_id in models.items():
        md_id = file_ids["md"]
        if not md_id:
            report.add(
                ProbeResult(
                    id=f"dashscope.chat_{model_key}_fileid_md_long",
                    label=f"{model_id} + fileid:// MD (long)",
                    status=ProbeStatus.SKIP,
                    detail="md file_id unavailable",
                )
            )
            continue

        async def chat_fileid_md_long(mid=model_id, fid=md_id) -> dict[str, Any]:
            messages = [
                {"role": "system", "content": "You are a document QA assistant."},
                fileid_system_message(fid),
                {
                    "role": "user",
                    "content": (
                        f"Quote the exact unique token from the document. "
                        f"It looks like PROBE_MD_SENTINEL_* — reply with the full token only."
                    ),
                },
            ]
            resp = await client.chat_completions(model=mid, messages=messages)
            text = OpenAICompatibleClient.assistant_text(resp)
            if PROBE_MD_SENTINEL not in text:
                raise RuntimeError(f"sentinel missing in response: {text[:300]!r}")
            return {"model": mid, "response_preview": text[:200]}

        await _run_probe(
            report,
            probe_id=f"dashscope.chat_{model_key}_fileid_md_long",
            label=f"{model_id} + fileid:// MD (long doc)",
            coro_factory=chat_fileid_md_long,
        )

    # Short MD + fileid (control — same upload path, smaller payload)
    short_md_upload: dict[str, Any] | None = None

    async def upload_short_md() -> dict[str, Any]:
        nonlocal short_md_upload
        short_md_upload = await client.upload_file(
            filename="probe-short.md",
            data=make_probe_markdown(long=False),
            mime_type="text/markdown",
            purpose="file-extract",
        )
        await client.wait_file_processed(str(short_md_upload["id"]))
        return {"file_id": short_md_upload["id"]}

    await _run_probe(
        report,
        probe_id="dashscope.upload_short_md",
        label="DashScope upload short MD (file-extract)",
        coro_factory=upload_short_md,
    )

    if short_md_upload:
        short_id = str(short_md_upload["id"])
        for model_key, model_id in models.items():
            async def chat_fileid_md_short(mid=model_id, fid=short_id) -> dict[str, Any]:
                messages = [
                    {"role": "system", "content": "You are a document QA assistant."},
                    fileid_system_message(fid),
                    {
                        "role": "user",
                        "content": "Quote the exact PROBE_MD_SENTINEL token from the file.",
                    },
                ]
                resp = await client.chat_completions(model=mid, messages=messages)
                text = OpenAICompatibleClient.assistant_text(resp)
                if PROBE_MD_SENTINEL not in text:
                    raise RuntimeError(f"short md fileid failed: {text[:300]!r}")
                return {"model": mid, "response_preview": text[:200]}

            await _run_probe(
                report,
                probe_id=f"dashscope.chat_{model_key}_fileid_md_short",
                label=f"{model_id} + fileid:// MD (short doc)",
                coro_factory=chat_fileid_md_short,
            )

    # PDF + fileid (uploaded via file-extract)
    pdf_id = file_ids.get("pdf")
    if pdf_id:
        for model_key, model_id in models.items():
            if model_key == "qwen_long":
                continue

            async def chat_fileid_pdf(mid=model_id, fid=pdf_id) -> dict[str, Any]:
                messages = [
                    {"role": "system", "content": "You are a document QA assistant."},
                    fileid_system_message(fid),
                    {
                        "role": "user",
                        "content": f"Quote exact token {PROBE_PDF_SENTINEL}",
                    },
                ]
                resp = await client.chat_completions(model=mid, messages=messages)
                text = OpenAICompatibleClient.assistant_text(resp)
                if PROBE_PDF_SENTINEL not in text:
                    raise RuntimeError(f"pdf fileid failed: {text[:300]!r}")
                return {"model": mid, "response_preview": text[:200]}

            await _run_probe(
                report,
                probe_id=f"dashscope.chat_{model_key}_fileid_pdf",
                label=f"{model_id} + fileid:// PDF (file-extract upload)",
                coro_factory=chat_fileid_pdf,
            )

    # --- PDF file_data probes (official OpenAI-compatible format) ---
    pdf_bytes = make_minimal_pdf()
    file_part = openai_pdf_file_data_part(pdf_bytes=pdf_bytes, filename="probe.pdf")

    for model_key, model_id in models.items():
        if model_key == "qwen_long":
            continue  # qwen-long uses fileid, not file_data

        async def chat_pdf_file_data(mid=model_id, part=file_part) -> dict[str, Any]:
            messages = [
                {
                    "role": "user",
                    "content": [
                        part,
                        {
                            "type": "text",
                            "text": (
                                f"What is the exact PROBE_PDF_SENTINEL token in this PDF? "
                                f"Reply with the full token only."
                            ),
                        },
                    ],
                }
            ]
            resp = await client.chat_completions(model=mid, messages=messages)
            text = OpenAICompatibleClient.assistant_text(resp)
            if PROBE_PDF_SENTINEL not in text:
                raise RuntimeError(f"pdf sentinel missing: {text[:300]!r}")
            return {"model": mid, "response_preview": text[:200]}

        await _run_probe(
            report,
            probe_id=f"dashscope.chat_{model_key}_pdf_file_data",
            label=f"{model_id} + PDF file_data (OpenAI file part)",
            coro_factory=chat_pdf_file_data,
        )

    # Baseline: qwen-long + fileid (official consumer)
    if "qwen_long" in models and file_ids["md"]:
        md_id = file_ids["md"]

        async def chat_qwen_long() -> dict[str, Any]:
            messages = [
                {"role": "system", "content": "You are a document QA assistant."},
                fileid_system_message(md_id),
                {
                    "role": "user",
                    "content": f"Quote the token containing {PROBE_MD_SENTINEL[:12]} exactly.",
                },
            ]
            resp = await client.chat_completions(model=models["qwen_long"], messages=messages)
            text = OpenAICompatibleClient.assistant_text(resp)
            if PROBE_MD_SENTINEL not in text:
                raise RuntimeError(f"qwen-long baseline failed: {text[:300]!r}")
            return {"response_preview": text[:200]}

        await _run_probe(
            report,
            probe_id="dashscope.chat_qwen_long_fileid_baseline",
            label="qwen-long + fileid:// MD (official baseline)",
            coro_factory=chat_qwen_long,
        )

    return file_ids

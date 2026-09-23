"""Live probes against DeepSeek Files + Chat API."""

from __future__ import annotations

import time
from typing import Any

from scripts.probe_file_api_phase0.fixtures import make_minimal_pdf, make_tiny_png
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


async def run_deepseek_probes(
    client: OpenAICompatibleClient,
    report: ProbeReport,
    *,
    chat_model: str,
) -> None:
    image_file_id: str | None = None

    async def upload_image() -> dict[str, Any]:
        payload = await client.upload_file(
            filename="probe.png",
            data=make_tiny_png(),
            mime_type="image/png",
            purpose="user_data",
        )
        nonlocal image_file_id
        image_file_id = str(payload["id"])
        return {"file_id": payload["id"]}

    await _run_probe(
        report,
        probe_id="deepseek.upload_image",
        label="DeepSeek upload PNG (purpose=user_data)",
        coro_factory=upload_image,
    )

    async def upload_pdf_expect_fail() -> dict[str, Any]:
        try:
            await client.upload_file(
                filename="probe.pdf",
                data=make_minimal_pdf(),
                mime_type="application/pdf",
                purpose="user_data",
            )
        except RuntimeError as exc:
            msg = str(exc).lower()
            if "pdf" in msg or "image" in msg or "400" in msg or "415" in msg:
                return {"rejected_as_expected": True, "error": str(exc)[:400]}
            raise
        raise RuntimeError("PDF upload unexpectedly succeeded")

    await _run_probe(
        report,
        probe_id="deepseek.upload_pdf_rejected",
        label="DeepSeek upload PDF (expect reject — images only)",
        coro_factory=upload_pdf_expect_fail,
    )

    if image_file_id:

        async def chat_image_file_id() -> dict[str, Any]:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in one word."},
                        {"type": "file", "file_id": image_file_id},
                    ],
                }
            ]
            resp = await client.chat_completions(model=chat_model, messages=messages)
            text = OpenAICompatibleClient.assistant_text(resp)
            if not text.strip():
                raise RuntimeError("empty response for image file_id chat")
            return {"response_preview": text[:200]}

        await _run_probe(
            report,
            probe_id="deepseek.chat_image_file_id",
            label=f"{chat_model} + image file_id",
            coro_factory=chat_image_file_id,
        )

    async def chat_pdf_inline_data() -> dict[str, Any]:
        """Probe whether deepseek-flash accepts inline PDF at all (likely fail)."""
        from scripts.probe_file_api_phase0.fixtures import openai_pdf_file_data_part, PROBE_PDF_SENTINEL, make_minimal_pdf

        part = openai_pdf_file_data_part(pdf_bytes=make_minimal_pdf())
        messages = [
            {
                "role": "user",
                "content": [
                    part,
                    {"type": "text", "text": f"Quote token {PROBE_PDF_SENTINEL}"},
                ],
            }
        ]
        resp = await client.chat_completions(model=chat_model, messages=messages)
        text = OpenAICompatibleClient.assistant_text(resp)
        if PROBE_PDF_SENTINEL not in text:
            raise RuntimeError(f"inline pdf not understood: {text[:300]!r}")
        return {"response_preview": text[:200]}

    await _run_probe(
        report,
        probe_id="deepseek.chat_pdf_file_data",
        label=f"{chat_model} + PDF file_data inline (probe)",
        coro_factory=chat_pdf_inline_data,
    )

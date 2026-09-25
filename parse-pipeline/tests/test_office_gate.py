from __future__ import annotations

from parse_pipeline.quality.docx_probe import DocxProbe
from parse_pipeline.quality.office_gate import GateDecision, evaluate_office_markdown


def _probe(**kwargs: object) -> DocxProbe:
    defaults = {
        "file_size": 50_000,
        "text_chars": 1000,
        "paragraph_count": 20,
        "table_count": 0,
        "image_count": 0,
        "heading_style_count": 0,
        "has_legacy_doc": False,
    }
    defaults.update(kwargs)
    return DocxProbe(**defaults)  # type: ignore[arg-type]


def test_gate_accepts_clean_markdown() -> None:
    content = "# Title\n\nSome readable paragraph with enough text.\n"
    result = evaluate_office_markdown(content, probe=_probe(text_chars=100))
    assert result.decision == GateDecision.ACCEPT


def test_gate_fallback_on_truncated_images() -> None:
    content = "![](data:image/png;base64...)\n"
    result = evaluate_office_markdown(content, probe=_probe(image_count=1))
    assert result.decision == GateDecision.FALLBACK
    assert "no_truncated_images" in result.fallback_reasons()


def test_gate_fallback_on_low_image_retention() -> None:
    content = "text only\n" * 20
    probe = _probe(image_count=20, text_chars=500)
    result = evaluate_office_markdown(content, probe=probe)
    assert result.decision == GateDecision.FALLBACK
    assert "image_retention" in result.fallback_reasons()

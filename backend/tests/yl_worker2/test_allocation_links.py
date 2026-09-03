"""Unit tests for OIP ↔ mock linking helpers."""

from app.yl_worker2.allocation_links import (
    embed_mock_no,
    extract_mock_no,
    is_cancelled_remark,
    mark_cancelled_remark,
)


def test_embed_and_extract_mock_no():
    remark = embed_mock_no("OIP-S1:草案", "BR-OIP-FWD-ABC")
    assert extract_mock_no(remark) == "BR-OIP-FWD-ABC"
    assert embed_mock_no(remark, "OTHER") == remark


def test_cancelled_remark():
    marked = mark_cancelled_remark("草案")
    assert is_cancelled_remark(marked)
    assert not is_cancelled_remark("草案")

"""Unit tests for entity mention scoring."""

from app.yl_worker2.runtime.entity_resolver import (
    build_resolution,
    normalize_mention,
    score_product_row,
    score_warehouse_row,
)


def test_normalize_mention_strips_warehouse_suffix():
    assert normalize_mention("郑州仓") == "郑州"
    assert normalize_mention("天津基地仓") == "天津"


def test_score_warehouse_zhengzhou():
    row = {"site_code": "MOCK_WH_S04", "site_name": "郑州销售仓", "site_desc": "河南郑州"}
    conf, method = score_warehouse_row("郑州仓", row)
    assert conf >= 0.85
    assert "warehouse" in method


def test_score_product_jinguangguan():
    row = {
        "product_code": "MOCK_YLP001",
        "product_name": "金领冠珍护1段婴儿配方奶粉(测试)",
        "brand": "金领冠",
        "pro_series": "金领冠珍护系列",
    }
    conf, method = score_product_row("金领冠", row)
    assert conf >= 0.8


def test_score_product_code_fragment():
    row = {
        "product_code": "MOCK_YLP001",
        "product_name": "伊利牛奶片32g原味(袋装)",
        "brand": "伊利",
    }
    conf, method = score_product_row("YLP001", row)
    assert conf >= 0.9
    assert "product_code" in method


def test_build_resolution_resolved():
    ranked = [
        {
            "site_code": "MOCK_WH_S04",
            "site_name": "郑州销售仓",
            "confidence": 0.92,
            "match_method": "warehouse.site_name_contains",
        }
    ]
    out = build_resolution("Warehouse", "郑州", ranked, id_key="site_code", display_key="site_name")
    assert out["status"] == "resolved"
    assert out["resolved_id"] == "MOCK_WH_S04"


def test_build_resolution_ambiguous():
    ranked = [
        {
            "site_code": "MOCK_WH_S02",
            "site_name": "天津销售仓",
            "confidence": 0.9,
            "match_method": "a",
        },
        {
            "site_code": "MOCK_WH_B02",
            "site_name": "天津基地仓",
            "confidence": 0.88,
            "match_method": "b",
        },
    ]
    out = build_resolution("Warehouse", "天津", ranked, id_key="site_code", display_key="site_name")
    assert out["status"] == "ambiguous"
    assert out["resolved_id"] is None
    assert len(out["candidates"]) >= 2

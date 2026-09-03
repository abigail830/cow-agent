"""Base routing lead time enrichment."""

from app.yl_worker2.runtime.base_routing import enrich_base_rows, lead_time_days


def test_lead_time_tianjin_to_zhengzhou():
    assert lead_time_days("MOCK_WH_B02", "MOCK_WH_S04") == 2


def test_enrich_sorts_by_lead_time():
    rows = [
        {"from_site_code": "MOCK_WH_B01", "from_available": 5000},
        {"from_site_code": "MOCK_WH_B02", "from_available": 8000},
    ]
    enriched = enrich_base_rows(rows, "MOCK_WH_S04")
    assert enriched[0]["from_site_code"] == "MOCK_WH_B02"
    assert enriched[0]["lead_time_days"] == 2

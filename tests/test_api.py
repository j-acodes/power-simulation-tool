"""API tests for the M0 FastAPI backend (catalogue + Stage-1 solve)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app, db
from backend.solve import build_chain
from powertool import size_pv_inverters

client = TestClient(app)

# The example-plant payload, ported from the deleted Streamlit app's load_example()
# and its sidebar defaults (45 MW POC, pf_target 0.95 — NOT 1.0; the
# Streamlit sidebar default was 0.95, confirmed against b5fc748).
EXAMPLE_ELEMENTS = [
    {"type": "Cable section", "v_kv": 20.0, "label": "MV collector"},
    {"type": "Transformer", "component": "HUAWEI_JUPITER9000", "v_kv": 20.0,
     "n_parallel": 5, "label": "MV/LV stations (big)"},
    {"type": "Transformer", "component": "HUAWEI_JUPITER3000", "v_kv": 20.0,
     "n_parallel": 3, "label": "MV/LV stations (small)"},
    {"type": "Aux load", "v_kv": 20.0, "p_kw": 120.0, "q_kvar": 40.0,
     "label": "Substation aux"},
]

EXAMPLE_PAYLOAD = {
    "p_poc_kw": 45000.0,
    "pf_target": 0.95,
    "interconnection": "HV",
    "v_export_kv": 132.0,
    "export_m": 0.0,
    "elements": EXAMPLE_ELEMENTS,
}


def test_catalogue_returns_transformers_cables_and_defaults():
    resp = client.get("/api/catalogue")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["transformers"]) >= 10
    for tx in data["transformers"]:
        assert tx["key"]
        assert tx["display_name"]
        assert tx["s_rated_kva"] > 0
        assert tx["uk_percent"] > 0
        assert tx["pk_kw"] >= 0
        assert tx["p0_kw"] >= 0
        assert tx["i0_percent"] >= 0

    assert data["cables"]
    for group, cables in data["cables"].items():
        assert cables  # every voltage-class group is non-empty
        for c in cables:
            assert c["name"]

    assert data["defaults"]["tiers"]["mv_kv"] == 20.0
    assert data["defaults"]["rules"]["max_utilization"] == 0.80


def test_stage1_example_plant_matches_direct_engine_computation():
    resp = client.post("/api/stage1", json=EXAMPLE_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()

    assert data["power_balance_ok"] is True
    assert data["s_inv_kva"] > EXAMPLE_PAYLOAD["p_poc_kw"]
    assert data["p_inv_kw"] > 45000.0

    # Self-consistency: the API's numbers must equal a direct engine
    # computation using the same ported build_chain + size_pv_inverters.
    chain = build_chain(
        EXAMPLE_ELEMENTS,
        db,
        interconnection="HV",
        v_export_kv=132.0,
        export_m=0.0,
        p_poc_kw=45000.0,
        pf_target=0.95,
    )
    expected = size_pv_inverters(chain, p_poc_kw=45000.0, pf_target=0.95)

    assert data["p_inv_kw"] == expected.p_inv_kw
    assert data["q_inv_kvar"] == expected.q_inv_kvar
    assert data["s_inv_kva"] == expected.s_inv_kva
    assert data["pf_inv"] == expected.pf_inv
    assert len(data["losses"]) == len(expected.losses)
    for got, exp in zip(data["losses"], expected.losses):
        assert got["label"] == exp.name
        assert got["dp_kw"] == exp.dp_kw
        assert got["dq_kvar"] == exp.dq_kvar


_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@pytest.mark.skipif(
    not _FRONTEND_DIST.is_dir(),
    reason="frontend/dist not present"
)
def test_spa_fallback_returns_index_html_for_client_routes():
    """SPA fallback: GET /design/123 returns 200 with index.html content."""
    resp = client.get("/design/123")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_api_nonexistent_returns_404():
    """Non-existent API endpoint returns 404."""
    resp = client.get("/api/nonexistent")
    assert resp.status_code == 404


def test_stage1_element_with_null_label_returns_200():
    """Regression test: POST /api/stage1 with null label should return 200, not 500."""
    payload = {
        "p_poc_kw": 45000.0,
        "pf_target": 0.95,
        "interconnection": "HV",
        "v_export_kv": 132.0,
        "export_m": 0.0,
        "elements": [
            {"type": "Cable section", "v_kv": 20.0, "label": None},
            {"type": "Transformer", "component": "HUAWEI_JUPITER9000", "v_kv": 20.0,
             "n_parallel": 1, "label": None},
        ],
    }
    resp = client.post("/api/stage1", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "losses" in data
    # Verify losses have empty string labels (not None)
    for loss in data["losses"]:
        assert isinstance(loss["label"], str)


# --- PDF report ---------------------------------------------------------------

def _example_diagram() -> dict:
    """The seeded 45 MW plant — a diagram that solves, built by the seeder."""
    from backend.seed import seed_diagram

    return seed_diagram(
        {"p_poc_mw": 45, "pf_target": 0.95, "interconnection": "HV", "v_hv_kv": 132,
         "export_m": 0, "v_mv_kv": 20, "station_model": "HUAWEI_JUPITER9000",
         "max_loading": 0.9, "trunk_m": 400, "spacing_m": 200,
         "max_circuit_current_a": 600, "aux_p_kw": 120, "aux_q_kvar": 40},
        db,
    )


def test_report_returns_a_pdf():
    resp = client.post("/api/report", json=_example_diagram(), params={"name": "Test Plant"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    assert "Test-Plant-sizing-report.pdf" in resp.headers["content-disposition"]


def test_report_filename_slug_strips_unsafe_characters():
    """The plant name reaches the Content-Disposition header — it must not be
    able to inject quotes or newlines."""
    resp = client.post(
        "/api/report",
        json=_example_diagram(),
        params={"name": 'ev"il\r\nX-Injected: 1'},
    )
    assert resp.status_code == 200
    disposition = resp.headers["content-disposition"]
    assert '"' not in disposition.split("filename=")[1].strip('"')
    assert "\n" not in disposition
    assert "X-Injected" not in resp.headers


def test_report_on_an_unsolvable_diagram_is_400():
    """An empty diagram has no POC — a validation issue, not a server error."""
    resp = client.post("/api/report", json={"schema_version": 1, "nodes": [], "edges": []})
    assert resp.status_code == 400
    assert resp.json()["detail"]

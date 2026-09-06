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


def test_catalogue_serves_the_reshaped_bess_solution():
    resp = client.get("/api/catalogue")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["bess_solutions"]) == 1
    sol = data["bess_solutions"][0]
    assert sol["key"] == "sungrow-st6900ux-4h"
    assert sol["display_name"] == "PowerTitan 3.0 — ST6900UX-4H"
    assert sol["brand"] == "Sungrow"
    assert sol["series"] == "PowerTitan 3.0"
    assert sol["model"] == "ST6900UX-4H"
    assert sol["e_nominal_kwh"] == 6904.0
    assert sol["pcs_s_kva"] == 450.0
    assert sol["pcs_count"] == 4
    assert sol["pcs_lv_kv"] == 0.69
    assert sol["duration_h"] == 4.0
    # Not published: null on the wire, not zero (ticket 07).
    assert sol["aux_p_kw"] is None
    assert sol["aux_q_kvar"] is None
    assert sol["preliminary"] is True
    # The reshaped fields are gone from the wire contract entirely.
    assert "containers_by_duration" not in sol
    assert "e_container_kwh" not in sol
    assert "pcs_p_kw" not in sol
    assert "containers_per_station" not in sol


def test_catalogue_serves_the_bess_solution_typed_specification():
    # The typed tier (ticket 04): structured, stored, displayed, never
    # computed with — see CONTEXT.md's "Simulated parameter / typed
    # parameter" entry. Transcribed from the Sungrow ST6900UX-4H datasheet.
    resp = client.get("/api/catalogue")
    assert resp.status_code == 200
    data = resp.json()

    sol = data["bess_solutions"][0]
    assert sol["cell_type"] == "LFP"
    assert sol["dc_v_min"] == 1101.6
    assert sol["dc_v_max"] == 1489.2
    assert sol["ac_v_min"] == 621.0
    assert sol["ac_v_max"] == 759.0
    assert sol["ac_i_a"] == 414.0
    assert sol["pf_at_nominal"] == 0.99
    assert sol["q_range_percent"] == 100.0
    assert sol["f_nominal_hz"] == "50 / 60"
    assert sol["thdi_percent"] == 1.0
    assert sol["isolation"] == "Transformerless"
    assert sol["width_mm"] == 6058
    assert sol["height_mm"] == 2896
    assert sol["depth_mm"] == 2438
    assert sol["weight_kg"] == 55000
    assert sol["ip_rating"] == "IP55"
    assert sol["corrosion_class"] == "C4"
    assert sol["temp_min_c"] == -30.0
    assert sol["temp_max_c"] == 45.0
    assert sol["humidity_min_pct"] == 0.0
    assert sol["humidity_max_pct"] == 100.0
    assert sol["altitude_max_m"] == 4000.0
    assert sol["cooling"] == "Intelligent Liquid Cooling"
    # There is no free-form/untyped tier: every field is a named, typed key.
    assert "spec" not in sol
    assert "specifications" not in sol


def test_catalogue_serves_bess_transformer_typed_fields():
    # A BESS station transformer's typed tier (ticket 04): model, vector
    # group, cooling, datasheet URL. Placeholder data leaves them unset.
    resp = client.get("/api/catalogue")
    assert resp.status_code == 200
    data = resp.json()

    by_key = {tx["key"]: tx for tx in data["bess_transformers"]}
    tx = by_key["GENERIC_BESS_TX_2750_LV069"]
    assert tx["model"] is None
    assert tx["vector_group"] is None
    assert tx["cooling"] is None
    assert tx["datasheet_url"] is None

    # A PV transformer carries the same fields, shared type, also unset.
    pv = data["transformers"][0]
    assert pv["model"] is None
    assert pv["vector_group"] is None
    assert pv["cooling"] is None
    assert pv["datasheet_url"] is None


def test_catalogue_serves_the_bess_station_transformer_pairing():
    # The pairing lives on the station transformer (ticket 02): a BESS
    # solution key -> containers per station, so the durations and solutions
    # on offer can be narrowed from the transformer side.
    resp = client.get("/api/catalogue")
    assert resp.status_code == 200
    data = resp.json()

    by_key = {tx["key"]: tx for tx in data["bess_transformers"]}
    assert by_key["GENERIC_BESS_TX_2750_LV069"]["paired_solutions"] == {
        "sungrow-st6900ux-4h": 1
    }
    assert by_key["GENERIC_BESS_TX_4000_LV069"]["paired_solutions"] == {
        "sungrow-st6900ux-4h": 2
    }
    # Deliberately unpaired — exercises bess_lv_mismatch.
    assert by_key["GENERIC_BESS_TX_1750_LV100"]["paired_solutions"] == {}

    # A PV transformer carries the same field, always empty: it has no
    # pairing to carry, but TransformerInfo is shared with the BESS catalogue.
    pv = data["transformers"][0]
    assert pv["paired_solutions"] == {}


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

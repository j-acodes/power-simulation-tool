"""API tests for the M0 FastAPI backend (catalogue + Stage-1 solve)."""

from fastapi.testclient import TestClient

from backend.main import app, db
from backend.solve import build_chain
from powertool import size_pv_inverters

client = TestClient(app)

# The example-plant payload, ported from app/streamlit_app.py:load_example()
# and its sidebar defaults (45 MW POC, pf_target 0.95 — NOT 1.0; the
# Streamlit sidebar default is 0.95, confirmed by reading the source).
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

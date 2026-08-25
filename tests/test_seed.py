"""Tests for the seed wizard (backend.seed.seed_diagram) and POST /api/seed.

Pinned here:

  * a seeded diagram is always VALID (``validate_graph`` returns no issues);
  * it SOLVES to a plant that meets the POC target within tolerance and does
    not overload the fleet;
  * seeding is deterministic (same params -> the same diagram) and every
    circuit respects the current cap it was seeded with;
  * the MV-interconnection variant (no hv_tx node) also validates and solves.
"""

from fastapi.testclient import TestClient

from backend.main import app, db
from backend.seed import seed_diagram
from backend.solve import solve_diagram
from powertool.graph import validate_graph

client = TestClient(app)

# The 45 MW reference plant: a single catalogue model, HV interconnection at
# 132 kV, 20 kV MV collection, the Stage-2 planning cap of 400 A per circuit,
# and the example plant's trunk/spacing (see frontend/src/example.ts).
REFERENCE_PARAMS = {
    "p_poc_mw": 45.0,
    "pf_target": 0.95,
    "interconnection": "HV",
    "v_hv_kv": 132.0,
    "export_m": 0.0,
    "v_mv_kv": 20.0,
    "station_model": "HUAWEI_JUPITER9000",
    "max_loading": 1.0,
    "trunk_m": 800.0,
    "spacing_m": 350.0,
    "max_circuit_current_a": 400.0,
}


def test_seed_reference_plant_is_valid():
    diagram = seed_diagram(REFERENCE_PARAMS, db)
    assert validate_graph(diagram, db) == []

    # HV interconnection: hv_tx node present, exactly one station model drawn.
    kinds = {n["id"]: n["kind"] for n in diagram["nodes"]}
    assert kinds["poc"] == "poc"
    assert kinds["hv_tx"] == "hv_tx"
    assert kinds["busbar"] == "busbar"
    station_ids = [nid for nid, kind in kinds.items() if kind == "station"]
    assert station_ids
    for node in diagram["nodes"]:
        if node["kind"] == "station":
            assert node["props"]["model"] == "HUAWEI_JUPITER9000"


def test_seed_reference_plant_solves_within_target_and_loading():
    diagram = seed_diagram(REFERENCE_PARAMS, db)
    result = solve_diagram(diagram, db)
    assert result["issues"] == []
    summary = result["results"]["summary"]

    p_target_kw = REFERENCE_PARAMS["p_poc_mw"] * 1000.0
    delivered = summary["p_poc_refined_delivered_kw"]
    assert delivered is not None
    assert delivered >= p_target_kw  # the engine never undershoots the target
    assert delivered <= p_target_kw * 1.005  # ... and not by more than 0.5 %

    assert summary["loading_ok"]
    assert summary["fleet_loading"] <= REFERENCE_PARAMS["max_loading"] + 1e-6


def test_seed_via_api_matches_direct_call():
    payload = {
        "p_poc_mw": REFERENCE_PARAMS["p_poc_mw"],
        "pf_target": REFERENCE_PARAMS["pf_target"],
        "interconnection": REFERENCE_PARAMS["interconnection"],
        "v_hv_kv": REFERENCE_PARAMS["v_hv_kv"],
        "export_m": REFERENCE_PARAMS["export_m"],
        "v_mv_kv": REFERENCE_PARAMS["v_mv_kv"],
        "station_model": REFERENCE_PARAMS["station_model"],
        "max_loading": REFERENCE_PARAMS["max_loading"],
        "trunk_m": REFERENCE_PARAMS["trunk_m"],
        "spacing_m": REFERENCE_PARAMS["spacing_m"],
        "max_circuit_current_a": REFERENCE_PARAMS["max_circuit_current_a"],
    }
    resp = client.post("/api/seed", json=payload)
    assert resp.status_code == 200
    diagram = resp.json()
    assert diagram == seed_diagram(REFERENCE_PARAMS, db)

    solve_resp = client.post("/api/solve", json=diagram)
    assert solve_resp.status_code == 200
    body = solve_resp.json()
    assert body["issues"] == []


def test_seeding_is_deterministic_and_circuits_respect_the_current_cap():
    first = seed_diagram(REFERENCE_PARAMS, db)
    second = seed_diagram(REFERENCE_PARAMS, db)
    assert first == second

    result = solve_diagram(first, db)
    assert result["issues"] == []
    summary = result["results"]["summary"]
    assert summary["all_current_ok"]
    assert summary["worst_trunk_current_a"] <= REFERENCE_PARAMS["max_circuit_current_a"] + 1e-6
    assert result["results"]["warnings"] == []


def test_seed_mv_interconnection_variant_validates_and_solves():
    params = dict(REFERENCE_PARAMS)
    params["interconnection"] = "MV"
    params.pop("v_hv_kv")
    diagram = seed_diagram(params, db)
    assert validate_graph(diagram, db) == []

    kinds = {n["kind"] for n in diagram["nodes"]}
    assert "hv_tx" not in kinds
    assert diagram["settings"]["tiers"]["hv_kv"] is None

    result = solve_diagram(diagram, db)
    assert result["issues"] == []
    summary = result["results"]["summary"]
    p_target_kw = params["p_poc_mw"] * 1000.0
    assert summary["p_poc_refined_delivered_kw"] >= p_target_kw
    assert summary["loading_ok"]


def test_seed_with_aux_load_adds_an_aux_node():
    params = dict(REFERENCE_PARAMS)
    params["aux_p_kw"] = 120.0
    params["aux_q_kvar"] = 40.0
    diagram = seed_diagram(params, db)
    assert validate_graph(diagram, db) == []
    aux_nodes = [n for n in diagram["nodes"] if n["kind"] == "aux"]
    assert len(aux_nodes) == 1
    assert aux_nodes[0]["props"] == {"p_kw": 120.0, "q_kvar": 40.0}

    result = solve_diagram(diagram, db)
    assert result["issues"] == []

"""Tests for the seed wizard (backend.seed.seed_diagram) and POST /api/seed.

Pinned here:

  * a seeded diagram is always VALID (``validate_graph`` returns no issues);
  * it SOLVES to a plant that meets the POC target within tolerance and does
    not overload the fleet;
  * seeding is deterministic (same params -> the same diagram) and every
    station stays within its own switchgear rated current (ADR-0006);
  * the MV-interconnection variant (no hv_tx node) also validates and solves.
"""

from fastapi.testclient import TestClient

from backend.main import app, db
from backend.seed import seed_diagram
from backend.solve import solve_diagram
from powertool.graph import validate_graph

client = TestClient(app)

# The 45 MW reference plant: a single catalogue model, HV interconnection at
# 132 kV, 20 kV MV collection, and the example plant's trunk/spacing (see
# frontend/src/example.ts). Circuit grouping is bounded by the station's own
# switchgear rated current (ADR-0006), never a flat planning cap.
REFERENCE_PARAMS = {
    "p_poc_mw": 45.0,
    "pf_target": 0.95,
    "interconnection": "HV",
    "v_hv_kv": 132.0,
    "export_m": 0.0,
    "v_mv_kv": 20.0,
    "station_model": "SUNGROW_MVS8960",
    "pv_inverter": "sungrow-sg350hx-20",
    "inverter_count": 28,
    "max_loading": 1.0,
    "trunk_m": 800.0,
    "spacing_m": 350.0,
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
            assert node["props"]["model"] == REFERENCE_PARAMS["station_model"]


def test_seed_station_count_uses_selected_inverter_active_and_apparent_capacity():
    params = dict(REFERENCE_PARAMS)
    params.update({"p_poc_mw": 4.5, "pf_target": 0.8, "inverter_count": 5})

    diagram = seed_diagram(params, db)
    stations = [node for node in diagram["nodes"] if node["kind"] == "station"]

    # Five 320 kW inverters give 1.6 MW/MVA per station. Active duty alone
    # needs three stations, while the 0.8-PF apparent duty needs four. The
    # 8.96 MVA transformer station could carry the target in one unit, proving
    # transformer loading is not the station-count authority.
    assert len(stations) == 4
    assert all(node["props"]["pv_inverter"] == "sungrow-sg350hx-20" for node in stations)
    assert all(node["props"]["inverter_count"] == 5 for node in stations)

    result = solve_diagram(diagram, db)
    assert result["issues"] == []
    assert result["results"]["summary"]["loading_ok"] is True
    assert all(
        result["results"]["nodes"][node["id"]]["inverter_apparent_ok"] is True
        for node in stations
    )


def test_seed_station_count_uses_active_capacity_at_unity_power_factor():
    params = dict(REFERENCE_PARAMS)
    params.update({"p_poc_mw": 4.0, "pf_target": 1.0, "inverter_count": 5})

    diagram = seed_diagram(params, db)
    stations = [node for node in diagram["nodes"] if node["kind"] == "station"]

    # Three 1.6 MW station inverter fleets are needed after losses. The same
    # transformer station could carry the full target in one unit.
    assert len(stations) == 3
    result = solve_diagram(diagram, db)
    assert result["issues"] == []
    assert all(
        result["results"]["nodes"][node["id"]]["inverter_active_ok"] is True
        for node in stations
    )


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
        "pv_inverter": REFERENCE_PARAMS["pv_inverter"],
        "inverter_count": REFERENCE_PARAMS["inverter_count"],
        "max_loading": REFERENCE_PARAMS["max_loading"],
        "trunk_m": REFERENCE_PARAMS["trunk_m"],
        "spacing_m": REFERENCE_PARAMS["spacing_m"],
    }
    resp = client.post("/api/seed", json=payload)
    assert resp.status_code == 200
    diagram = resp.json()
    assert diagram == seed_diagram(REFERENCE_PARAMS, db)

    solve_resp = client.post("/api/solve", json=diagram)
    assert solve_resp.status_code == 200
    body = solve_resp.json()
    assert body["issues"] == []


def test_seed_api_rejects_count_above_the_station_pairing_maximum():
    payload = dict(REFERENCE_PARAMS)
    payload["inverter_count"] = 29

    resp = client.post("/api/seed", json=payload)

    assert resp.status_code == 400
    assert "1 to 28" in resp.json()["detail"]


def test_seeding_is_deterministic_and_every_station_respects_its_switchgear_rating():
    first = seed_diagram(REFERENCE_PARAMS, db)
    second = seed_diagram(REFERENCE_PARAMS, db)
    assert first == second

    result = solve_diagram(first, db)
    assert result["issues"] == []
    summary = result["results"]["summary"]
    assert summary["all_current_ok"]
    # The reference station publishes a switchgear rated current but no cable
    # entry yet (no on-file datasheet does) — the ADR-0007 fallback notice is
    # expected here; nothing else is.
    assert [w["code"] for w in result["results"]["warnings"]] == ["cable_entry_not_published"]


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

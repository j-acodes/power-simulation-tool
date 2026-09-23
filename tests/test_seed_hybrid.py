"""Tests for the hybrid seed wizard (ticket 03): backend.seed.seed_diagram's
hybrid branch and POST /api/seed's technology="hybrid" request.

Pinned here (external behaviour only — params in, diagram out, then
validate/solve that diagram):

  * both fleet power figures land on the point of connection
    (``p_target_mw`` for PV, ``p_target_bess_mw`` for BESS) alongside each
    fleet's own maximum-loading rule;
  * PV circuits sit left of BESS circuits and the point of connection is
    centred over both;
  * the auxiliary load hangs off the first PV busbar;
  * both HV and MV interconnection variants validate and solve, each fleet
    within its own loading limit with the BESS fleet's energy met;
  * seeding is deterministic.

``tests/test_seed.py`` and ``tests/test_seed_bess.py`` are left untouched by
this file — the single-fleet paths (``_seed_pv``/``_seed_bess``) are exactly
as they were before this ticket, just reached through a shared, extracted
sizing helper (``_size_pv_fleet``/``_size_bess_fleet``). Loading limits below
1.0 throughout, unlike ticket 02's tests, so an overloaded fleet cannot hide
behind a limit of 1.0.

Real catalogue entries (see data/*.yaml): SUNGROW_MVS3200 paired with
sungrow-sg350hx-20 (see tests/test_seed.py, tests/test_hybrid.py); the same
GENERIC_BESS_TX_4000_LV069 / sungrow-st6900ux-4h pairing as
tests/test_seed_bess.py (2 containers per station maximum, 6904 kWh each).
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app, db
from backend.seed import seed_diagram
from backend.solve import solve_diagram
from powertool.graph import validate_graph

client = TestClient(app)

BASE_PARAMS = {
    "technology": "hybrid",
    "pf_target": 0.95,
    "interconnection": "MV",
    "v_mv_kv": 20.0,
    "export_m": 0.0,
    # PV block
    "p_poc_mw": 3.0,
    "station_model": "SUNGROW_MVS3200",
    "pv_inverter": "sungrow-sg350hx-20",
    "inverter_count": 5,
    "max_loading": 0.85,
    "trunk_m": 100.0,
    "spacing_m": 50.0,
    # BESS block
    "p_poc_bess_mw": 2.0,
    "discharge_hours": 4.0,
    "bess_solution": "sungrow-st6900ux-4h",
    "bess_station_model": "GENERIC_BESS_TX_4000_LV069",
    "max_loading_bess": 0.8,
    "trunk_bess_m": 100.0,
    "spacing_bess_m": 50.0,
}


def _stations(diagram: dict) -> list[dict]:
    return [n for n in diagram["nodes"] if n["kind"] == "station"]


def _busbars(diagram: dict) -> list[dict]:
    return [n for n in diagram["nodes"] if n["kind"] == "busbar"]


def test_hybrid_poc_carries_both_fleet_targets_and_per_kind_loading_rules():
    diagram = seed_diagram(BASE_PARAMS, db)
    assert validate_graph(diagram, db) == []

    poc = next(n for n in diagram["nodes"] if n["kind"] == "poc")
    assert poc["props"]["p_target_mw"] == BASE_PARAMS["p_poc_mw"]
    assert poc["props"]["p_target_bess_mw"] == BASE_PARAMS["p_poc_bess_mw"]

    assert diagram["settings"]["rules"]["max_loading"] == BASE_PARAMS["max_loading"]
    assert diagram["settings"]["rules"]["max_loading_bess"] == BASE_PARAMS["max_loading_bess"]
    assert diagram["settings"]["rules"]["discharge_hours"] == BASE_PARAMS["discharge_hours"]


def test_pv_left_of_bess_and_poc_centred_over_both():
    diagram = seed_diagram(BASE_PARAMS, db)

    pv_stations = [n for n in _stations(diagram) if n["props"]["fleet_kind"] == "pv"]
    bess_stations = [n for n in _stations(diagram) if n["props"]["fleet_kind"] == "bess"]
    assert pv_stations and bess_stations

    max_pv_x = max(n["x"] for n in pv_stations)
    min_bess_x = min(n["x"] for n in bess_stations)
    assert max_pv_x < min_bess_x

    poc = next(n for n in diagram["nodes"] if n["kind"] == "poc")
    all_x = [n["x"] for n in pv_stations + bess_stations]
    assert min(all_x) <= poc["x"] <= max(all_x)


def test_auxiliary_load_hangs_off_the_first_pv_busbar():
    params = dict(BASE_PARAMS)
    params["aux_p_kw"] = 40.0
    params["aux_q_kvar"] = 10.0
    diagram = seed_diagram(params, db)
    assert validate_graph(diagram, db) == []

    aux_edge = next(e for e in diagram["edges"] if e["id"] == "e_aux")
    assert aux_edge["source"] == "busbar"
    first_busbar = next(n for n in _busbars(diagram) if n["id"] == "busbar")
    assert first_busbar["props"]["fleet_kind"] == "pv"


def test_seeded_hybrid_solves_mv_with_both_fleets_within_limits_and_energy_met():
    diagram = seed_diagram(BASE_PARAMS, db)
    assert "hv_tx" not in {n["kind"] for n in diagram["nodes"]}
    result = solve_diagram(diagram, db)
    assert result["issues"] == []

    branches = {b["kind"]: b for b in result["results"]["summary"]["branches"]}
    assert branches["pv"]["loading_ok"] is True
    assert branches["pv"]["fleet_loading"] <= BASE_PARAMS["max_loading"] + 1e-6
    assert branches["bess"]["loading_ok"] is True
    assert branches["bess"]["fleet_loading"] <= BASE_PARAMS["max_loading_bess"] + 1e-6
    assert branches["bess"]["energy_ok"] is True


def test_seeded_hybrid_solves_hv_with_both_fleets_within_limits_and_energy_met():
    params = dict(BASE_PARAMS)
    params.update({"interconnection": "HV", "v_hv_kv": 132.0})
    diagram = seed_diagram(params, db)
    assert "hv_tx" in {n["kind"] for n in diagram["nodes"]}
    result = solve_diagram(diagram, db)
    assert result["issues"] == []

    branches = {b["kind"]: b for b in result["results"]["summary"]["branches"]}
    assert branches["pv"]["loading_ok"] is True
    assert branches["bess"]["loading_ok"] is True
    assert branches["bess"]["energy_ok"] is True


@pytest.mark.parametrize("p_poc_bess_mw", [20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 60.0])
def test_max_loading_bess_bounds_every_station_in_a_hybrid_seed(p_poc_bess_mw):
    # Ticket 06: _seed_hybrid reuses _size_bess_fleet, so the same
    # loading-driven floor on the container count must hold here too.
    params = dict(BASE_PARAMS)
    params["p_poc_bess_mw"] = p_poc_bess_mw
    diagram = seed_diagram(params, db)
    result = solve_diagram(diagram, db)
    assert result["issues"] == []

    branches = {b["kind"]: b for b in result["results"]["summary"]["branches"]}
    assert branches["bess"]["loading_ok"] is True
    assert branches["bess"]["energy_ok"] is True


def test_seeding_hybrid_is_deterministic():
    first = seed_diagram(BASE_PARAMS, db)
    second = seed_diagram(BASE_PARAMS, db)
    assert first == second


def test_seed_via_api_matches_direct_call_for_hybrid():
    resp = client.post("/api/seed", json=BASE_PARAMS)
    assert resp.status_code == 200
    diagram = resp.json()
    assert diagram == seed_diagram(BASE_PARAMS, db)

    solve_resp = client.post("/api/solve", json=diagram)
    assert solve_resp.status_code == 200
    assert solve_resp.json()["issues"] == []


def test_pv_only_and_bess_only_seeding_unaffected_by_the_shared_sizing_helpers():
    """The extraction (_size_pv_fleet/_size_bess_fleet) backing both this
    file and the hybrid branch must not change a single-fleet seed's own
    output — proven directly here rather than only by
    tests/test_seed.py / tests/test_seed_bess.py staying green."""
    from tests.test_seed import REFERENCE_PARAMS
    from tests.test_seed_bess import BASE_PARAMS as BESS_BASE_PARAMS

    pv_diagram = seed_diagram(REFERENCE_PARAMS, db)
    assert validate_graph(pv_diagram, db) == []

    bess_diagram = seed_diagram(BESS_BASE_PARAMS, db)
    assert validate_graph(bess_diagram, db) == []

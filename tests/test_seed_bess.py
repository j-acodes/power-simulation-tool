"""Tests for the BESS seed wizard (ticket 02): backend.seed.seed_diagram's
BESS branch and POST /api/seed's technology-scoped SeedRequest.

Pinned here (external behaviour only — params in, diagram out, then
validate/solve that diagram):

  * container fill: stations run at the pairing maximum in circuit order,
    the remainder lands on the last one, and an override is written only
    where a station differs from the maximum;
  * an energy shortfall at the power-sized station count raises it until
    the fleet's own energy check (containers x e_nominal_kwh) is met;
  * the seeded diagram validates and solves with energy met and loading
    within the limit;
  * seeding is deterministic;
  * the request rejects a solution that does not sell the requested
    duration, a station not paired with the chosen solution, and (via
    Pydantic) a design whose declared technology needs a block it did not
    send.

Real catalogue entries (see data/bess.yaml, data/bess_transformers.yaml):
GENERIC_BESS_TX_4000_LV069 is paired with sungrow-st6900ux-4h at a maximum
of 2 containers per station (2 x 4 x 450 kVA = 3600 kW installed PCS);
GENERIC_BESS_TX_2750_LV069 with the same solution at a maximum of 1
(1 x 4 x 450 kVA = 1800 kW). Both stations' LV (0.69 kV) matches the
solution's PCS voltage, so the plant clears bess_lv_mismatch too.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app, db
from backend.schemas import SeedRequest
from backend.seed import seed_diagram
from backend.solve import solve_diagram
from powertool.graph import validate_graph

client = TestClient(app)

# 5 MW BESS-only design, MV interconnection: two GENERIC_BESS_TX_4000_LV069
# stations size the fleet's power (3600 kW installed PCS each), and 5 MW for
# 4 h needs ceil(5000*4/6904) = 3 containers — one full station (2) and the
# remainder (1) on the second, in circuit order.
BASE_PARAMS = {
    "technology": "bess",
    "pf_target": 1.0,
    "interconnection": "MV",
    "v_mv_kv": 20.0,
    "export_m": 0.0,
    "bess_station_model": "GENERIC_BESS_TX_4000_LV069",
    "bess_solution": "sungrow-st6900ux-4h",
    "discharge_hours": 4.0,
    "p_poc_bess_mw": 5.0,
    "max_loading_bess": 1.0,
    "trunk_bess_m": 500.0,
    "spacing_bess_m": 200.0,
}


def _stations(diagram: dict) -> list[dict]:
    return [n for n in diagram["nodes"] if n["kind"] == "station"]


def test_seed_bess_reference_plant_is_valid():
    diagram = seed_diagram(BASE_PARAMS, db)
    assert validate_graph(diagram, db) == []

    kinds = {n["id"]: n["kind"] for n in diagram["nodes"]}
    assert kinds["poc"] == "poc"
    assert "hv_tx" not in kinds  # MV interconnection
    assert kinds["busbar"] == "busbar"
    busbar = next(n for n in diagram["nodes"] if n["kind"] == "busbar")
    assert busbar["props"]["fleet_kind"] == "bess"
    for station in _stations(diagram):
        assert station["props"]["model"] == BASE_PARAMS["bess_station_model"]
        assert station["props"]["fleet_kind"] == "bess"
        assert station["props"]["bess_solution"] == BASE_PARAMS["bess_solution"]

    # The single-fleet BESS plant carries its target on p_target_mw (the
    # engine's own single-fleet reading — see graph_to_inputs and
    # tests/test_hybrid.py's _bess_only fixture), not p_target_bess_mw.
    poc = next(n for n in diagram["nodes"] if n["kind"] == "poc")
    assert poc["props"]["p_target_mw"] == BASE_PARAMS["p_poc_bess_mw"]

    assert diagram["settings"]["rules"]["discharge_hours"] == BASE_PARAMS["discharge_hours"]
    assert diagram["settings"]["rules"]["max_loading_bess"] == BASE_PARAMS["max_loading_bess"]
    assert diagram["settings"]["tiers"]["lv_kv"] == pytest.approx(0.69)


def test_container_fill_maximum_in_order_remainder_on_last():
    diagram = seed_diagram(BASE_PARAMS, db)
    stations = _stations(diagram)

    assert len(stations) == 2
    first, second = stations
    # First station stays at the pairing maximum: no override written.
    assert "containers_override" not in first["props"]
    # The remainder (3 - 2 = 1) lands on the last station, below the
    # maximum of 2, so it IS written.
    assert second["props"]["containers_override"] == 1


def test_energy_shortfall_at_the_maximum_adds_a_station():
    # GENERIC_BESS_TX_2750_LV069 x sungrow-st6900ux-4h: pairing maximum 1
    # container, 1800 kW installed PCS. 1.8 MW alone needs exactly one
    # station on power, but 1 container only delivers 6904 kWh against the
    # 1.8 MW x 4 h = 7200 kWh owed — the energy check forces a second
    # station even though the power-sized count was already met.
    params = dict(BASE_PARAMS)
    params.update({
        "bess_station_model": "GENERIC_BESS_TX_2750_LV069",
        "p_poc_bess_mw": 1.8,
    })
    diagram = seed_diagram(params, db)
    stations = _stations(diagram)

    assert len(stations) == 2
    for station in stations:
        # Required containers (2) divides evenly by the maximum (1), so
        # neither station needs an override — both stay at the default.
        assert "containers_override" not in station["props"]


def test_seeded_bess_plant_solves_with_energy_met_and_loading_within_limit():
    diagram = seed_diagram(BASE_PARAMS, db)
    result = solve_diagram(diagram, db)
    assert result["issues"] == []

    summary = result["results"]["summary"]
    assert summary["loading_ok"] is True
    assert summary["fleet_loading"] <= BASE_PARAMS["max_loading_bess"] + 1e-6

    branch = summary["branches"][0]
    assert branch["kind"] == "bess"
    assert branch["containers"] == 3
    assert branch["e_delivered_kwh"] == pytest.approx(3 * 6904.0)
    assert branch["e_required_kwh"] == pytest.approx(BASE_PARAMS["p_poc_bess_mw"] * 1000.0 * 4.0)
    assert branch["energy_ok"] is True


def test_max_loading_bess_bounds_the_station_count():
    # Browser repro (ticket 02 fix round): sizing the station count from
    # installed PCS alone gives 7 SUNGROW_MVS7400_LS stations here — 89 %
    # fleet loading, NOT COMPLIANT against the 80 % max_loading_bess limit.
    # The transformer's AC power at ambient x max_loading must also bound
    # the count, the same way _seed_pv already bounds PV station count.
    params = dict(BASE_PARAMS)
    params.update({
        "interconnection": "HV",
        "v_hv_kv": 132.0,
        "pf_target": 0.95,
        "bess_station_model": "SUNGROW_MVS7400_LS",
        "p_poc_bess_mw": 40.0,
        "max_loading_bess": 0.8,
        "trunk_bess_m": 800.0,
        "spacing_bess_m": 350.0,
        "aux_p_kw": 120.0,
        "aux_q_kvar": 40.0,
    })
    diagram = seed_diagram(params, db)
    result = solve_diagram(diagram, db)
    assert result["issues"] == []

    summary = result["results"]["summary"]
    assert summary["loading_ok"] is True
    assert summary["fleet_loading"] <= params["max_loading_bess"] + 1e-6

    branch = summary["branches"][0]
    assert branch["kind"] == "bess"
    assert branch["energy_ok"] is True


def test_seeding_bess_is_deterministic():
    first = seed_diagram(BASE_PARAMS, db)
    second = seed_diagram(BASE_PARAMS, db)
    assert first == second


def test_seed_via_api_matches_direct_call_for_bess():
    resp = client.post("/api/seed", json=BASE_PARAMS)
    assert resp.status_code == 200
    diagram = resp.json()
    assert diagram == seed_diagram(BASE_PARAMS, db)

    solve_resp = client.post("/api/solve", json=diagram)
    assert solve_resp.status_code == 200
    assert solve_resp.json()["issues"] == []


# --- request rejections ------------------------------------------------------

def test_api_rejects_a_solution_that_does_not_sell_the_requested_duration():
    # sungrow-st6680ux-2h sells 2 h, not the 4 h requested here — even though
    # SUNGROW_MVS7080_LS IS paired with it (see data/bess_transformers.yaml).
    params = dict(BASE_PARAMS)
    params.update({
        "bess_station_model": "SUNGROW_MVS7080_LS",
        "bess_solution": "sungrow-st6680ux-2h",
        "discharge_hours": 4.0,
    })
    resp = client.post("/api/seed", json=params)
    assert resp.status_code == 400
    assert "2 h" in resp.json()["detail"] and "4 h" in resp.json()["detail"]


def test_api_rejects_a_station_not_paired_with_the_chosen_solution():
    # GENERIC_BESS_TX_1750_LV100 carries no paired_solutions at all.
    params = dict(BASE_PARAMS)
    params["bess_station_model"] = "GENERIC_BESS_TX_1750_LV100"
    resp = client.post("/api/seed", json=params)
    assert resp.status_code == 400
    assert "not sold with" in resp.json()["detail"]


def test_pv_fields_are_required_only_when_technology_permits_pv():
    # technology="bess" (default request) needs no PV block at all.
    SeedRequest(**BASE_PARAMS)

    # technology="pv" (the default) still needs the PV block it always did.
    with pytest.raises(Exception):
        SeedRequest(pf_target=0.95, interconnection="MV", v_mv_kv=20.0, trunk_m=100.0, spacing_m=50.0)


def test_bess_fields_are_required_only_when_technology_permits_bess():
    # A plain PV request (today's shape, no `technology` key at all) needs
    # no BESS block.
    SeedRequest(
        p_poc_mw=10.0, pf_target=0.95, interconnection="MV", v_mv_kv=20.0,
        station_model="SUNGROW_MVS3200", pv_inverter="sungrow-sg350hx-20",
        inverter_count=5, trunk_m=100.0, spacing_m=50.0,
    )

    # technology="bess" without the BESS block is rejected.
    with pytest.raises(Exception):
        SeedRequest(technology="bess", pf_target=0.95, interconnection="MV", v_mv_kv=20.0)


def test_api_now_seeds_hybrid_instead_of_rejecting_it():
    # This test used to pin "technology=hybrid is a 400" (ticket 03 was out
    # of scope when it was written — see git history for the original
    # assertion). Ticket 03 lifted that refusal, so the premise this test
    # guards has flipped: hybrid is a supported technology now, seeded and
    # solved like PV or BESS. Full hybrid seed behaviour lives in
    # tests/test_seed_hybrid.py; this one only guards against the 400
    # regressing.
    params = dict(BASE_PARAMS)
    params.update({
        "technology": "hybrid",
        "p_poc_mw": 10.0, "station_model": "SUNGROW_MVS3200",
        "pv_inverter": "sungrow-sg350hx-20", "inverter_count": 5,
        "trunk_m": 100.0, "spacing_m": 50.0,
        "max_loading": 0.85,
        "max_loading_bess": 0.8,
    })
    resp = client.post("/api/seed", json=params)
    assert resp.status_code == 200
    solve_resp = client.post("/api/solve", json=resp.json())
    assert solve_resp.json()["issues"] == []

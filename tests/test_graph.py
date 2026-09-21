"""Tests for the diagram <-> engine mapping layer (powertool.graph) and /api/solve.

Two things are pinned here:

  * the VALIDATION contract — a drawing that breaks the topology rules comes
    back as issues keyed to the offending node/edge, never as an exception;
  * the GOLDEN equivalence — the 45 MW example plant, drawn on the canvas with
    the arrangement today's ``arrange_plant`` produces, must solve to exactly
    the numbers the auto path produces. The drawing changes WHO arranges the
    plant, never the physics.
"""

import math
from dataclasses import replace

import pytest

from fastapi.testclient import TestClient

from backend.main import app, db
from backend.solve import build_chain, solve_diagram
from powertool import (
    ComponentDatabase,
    arrange_plant,
    size_architecture,
    size_pv_inverters,
)
from powertool.graph import graph_to_inputs, map_results, supported_durations, validate_graph

client = TestClient(app)


# --- diagram builders -------------------------------------------------------

def _node(node_id: str, kind: str, **props) -> dict:
    # x/y are cosmetic (excluded from the solve hash) but always present on the
    # canvas payload, so the fixtures carry them too.
    return {"id": node_id, "kind": kind, "x": 0.0, "y": 0.0, "props": props}


def _edge(edge_id: str, source: str, target: str, *, tier: str = "mv",
          length_m: float | None = None, sizing: dict | None = None) -> dict:
    edge = {"id": edge_id, "source": source, "target": target, "tier": tier,
            "sizing": sizing or {"mode": "auto"}}
    if length_m is not None:
        edge["length_m"] = length_m
    return edge


def _settings(hv_kv: float | None = None) -> dict:
    return {
        "tiers": {"lv_kv": 0.8, "mv_kv": 20.0, "hv_kv": hv_kv},
        "rules": {"max_utilization": 0.80, "collection_loss_pct": 1.30,
                  "export_loss_pct_per_km": 0.10},
    }


def _minimal() -> dict:
    """The smallest solvable drawing: POC -- busbar (MV interconnection), one
    station on one circuit, one aux load."""
    return {
        "schema_version": 1,
        "settings": _settings(),
        "nodes": [
            _node("poc", "poc", p_target_mw=3.0, pf=0.95),
            _node("bus", "busbar"),
            _node(
                "s1", "station", mode="catalogue", model="HUAWEI_JUPITER3000",
                pv_inverter="huawei-sun2000-330ktl-h1", inverter_count=11,
            ),
            _node("aux", "aux", p_kw=50.0, q_kvar=10.0),
        ],
        "edges": [
            _edge("e_poc", "poc", "bus", length_m=0.0),
            _edge("e_t1", "bus", "s1", length_m=800.0),
            _edge("e_aux", "bus", "aux"),
        ],
    }


def _codes(issues) -> set[str]:
    return {issue.code for issue in issues}


# --- validation catalogue ---------------------------------------------------

def test_minimal_drawing_is_valid():
    assert validate_graph(_minimal(), db) == []


def test_pv_station_rejects_unknown_unpaired_and_out_of_range_inverters():
    diagram = _minimal()
    station = diagram["nodes"][2]["props"]
    station.pop("pv_inverter")
    station.pop("inverter_count")
    assert "unknown_pv_inverter" in _codes(validate_graph(diagram, db))
    rejected = client.post("/api/solve", json=diagram).json()
    assert rejected["results"] is None
    assert "unknown_pv_inverter" in {issue["code"] for issue in rejected["issues"]}

    station.update({"model": "SUNGROW_MVS3200", "pv_inverter": "missing", "inverter_count": 10})
    assert "unknown_pv_inverter" in _codes(validate_graph(diagram, db))

    station.update({"model": "HUAWEI_JUPITER3000", "pv_inverter": "sungrow-sg350hx-20"})
    assert "unpaired_pv_inverter" in _codes(validate_graph(diagram, db))

    station.update({"model": "SUNGROW_MVS3200", "pv_inverter": "sungrow-sg350hx-20"})
    station.pop("inverter_count")
    assert "bad_inverter_count" in _codes(validate_graph(diagram, db))
    station["inverter_count"] = 0
    assert "bad_inverter_count" in _codes(validate_graph(diagram, db))
    station["inverter_count"] = 11
    assert "bad_inverter_count" in _codes(validate_graph(diagram, db))


def test_station_without_fleet_kind_parses_as_pv_and_solves_identically():
    # This is the backward-compatibility guarantee for every design already
    # saved: a station that never heard of fleet_kind must behave exactly as
    # it did before this concept existed.
    diagram = _minimal()
    assert "fleet_kind" not in diagram["nodes"][2]["props"]
    without = client.post("/api/solve", json=diagram).json()

    explicit_pv = _minimal()
    explicit_pv["nodes"][2]["props"]["fleet_kind"] = "pv"
    with_pv = client.post("/api/solve", json=explicit_pv).json()

    assert without["issues"] == [] and without["results"] is not None
    assert without == with_pv

    # Comparing absent-kind against explicit "pv" only proves both take the
    # same branch. These are the numbers this design produced BEFORE fleet kind
    # existed, pinned so that any drift in the cascade shows up here and not
    # just as a diffuse failure somewhere in the rest of the suite.
    summary = without["results"]["summary"]
    assert summary["p_inv_kw"] == pytest.approx(3163.6147359619677)
    assert summary["q_inv_kvar"] == pytest.approx(1272.0934930043616)
    assert summary["s_inv_kva"] == pytest.approx(3409.791790203582)
    assert summary["correction_factor"] == pytest.approx(0.9785295710741883)
    assert summary["p_poc_refined_delivered_kw"] == pytest.approx(3000.0, rel=1e-6)


def test_single_fleet_solve_meets_active_and_reactive_poc_duty():
    result = client.post("/api/solve", json=_minimal()).json()
    assert result["issues"] == []
    summary = result["results"]["summary"]
    required_q = 3000.0 * math.tan(math.acos(0.95))
    assert summary["p_poc_refined_delivered_kw"] >= 3000.0 - 1e-6
    assert summary["q_poc_delivered_kvar"] == pytest.approx(required_q, rel=1e-5)
    station = result["results"]["nodes"]["s1"]
    cable = result["results"]["edges"]["e_t1"]
    assert station["loading"] == pytest.approx(summary["fleet_loading"])
    assert cable["current_a"] == pytest.approx(
        cable["s_kva"] / (math.sqrt(3.0) * 20.0))
    rated = db.cables["AL_95_20kV"].rated_current_a
    assert cable["utilization"] == pytest.approx(
        cable["current_a"] * cable["n_parallel"] / rated)
    assert cable["utilization"] <= 0.80
    assert cable["p_kw"] - cable["dp_kw"] == pytest.approx(
        result["results"]["nodes"]["bus"]["p_kw"])
    assert cable["q_kvar"] - cable["dq_series_kvar"] == pytest.approx(
        result["results"]["nodes"]["bus"]["q_kvar"])
    assert result["results"]["nodes"]["bus"]["p_kw"] - 50.0 == pytest.approx(
        summary["p_poc_delivered_kw"])
    assert result["results"]["nodes"]["bus"]["q_kvar"] - 10.0 == pytest.approx(
        summary["q_poc_delivered_kvar"])
    assert summary["power_balance_ok"] is True


def test_single_pv_fleet_at_unity_pf_delivers_zero_reactive_power():
    diagram = _minimal()
    diagram["nodes"][0]["props"]["pf"] = 1.0
    result = client.post("/api/solve", json=diagram).json()

    assert result["issues"] == []
    assert result["results"] is not None
    summary = result["results"]["summary"]
    assert summary["p_poc_refined_delivered_kw"] == pytest.approx(3000.0, abs=1e-3)
    assert summary["q_poc_delivered_kvar"] == pytest.approx(0.0, abs=1e-3)
    assert summary["power_balance_ok"] is True


def test_pv_station_duty_is_shared_by_installed_inverter_capacity():
    diagram = _minimal()
    diagram["nodes"][2]["props"].update({
        "model": "SUNGROW_MVS3200",
        "pv_inverter": "sungrow-sg350hx-20",
        "inverter_count": 10,
    })
    diagram["nodes"].append(_node(
        "s2", "station", mode="catalogue", model="SUNGROW_MVS3200",
        pv_inverter="sungrow-sg350hx-20", inverter_count=5,
    ))
    diagram["edges"].append(_edge("e_t2", "s1", "s2", length_m=400.0))

    result = client.post("/api/solve", json=diagram).json()

    assert result["issues"] == []
    stations = result["results"]["nodes"]
    assert stations["s1"]["p_lv_kw"] == pytest.approx(2 * stations["s2"]["p_lv_kw"])
    assert stations["s1"]["q_lv_kvar"] == pytest.approx(2 * stations["s2"]["q_lv_kvar"])


def test_pv_inverter_capacity_and_power_factor_violations_warn_but_return_results():
    diagram = _minimal()
    diagram["nodes"][0]["props"].update({"p_target_mw": 4.0, "pf": 0.75})
    diagram["nodes"][2]["props"].update({
        "model": "SUNGROW_MVS3200",
        "pv_inverter": "sungrow-sg350hx-20",
        "inverter_count": 10,
    })

    result = solve_diagram(diagram, db)

    assert result["issues"] == []
    assert result["results"] is not None
    station = result["results"]["nodes"]["s1"]
    assert station["inverter_capacity_kw"] == 3200
    assert station["inverter_active_ok"] is False
    assert station["inverter_apparent_ok"] is False
    assert station["inverter_power_factor_ok"] is False
    codes = {warning["code"] for warning in result["results"]["warnings"]}
    assert "inverter_active_capacity_exceeded" in codes
    assert "inverter_apparent_capacity_exceeded" in codes
    assert "inverter_power_factor_below_minimum" in codes


def test_circuit_over_switchgear_through_current_still_solves_flagged_at_offending_station():
    # A two-station daisy chain (ADR-0006): s1 sits nearest the busbar and
    # carries its own current plus s2's, downstream of it in the chain. Each
    # station's OWN current stays under its 630 A switchgear rating, but s1's
    # THROUGH current (both stations) does not — the circuit is collectively
    # too heavy, not self-contradictory, so it must still solve in full.
    diagram = _minimal()
    diagram["nodes"][0]["props"].update({"p_target_mw": 21.0, "pf": 0.95})
    diagram["nodes"][2]["props"].update({
        "model": "SUNGROW_MVS3200",
        "pv_inverter": "sungrow-sg350hx-20",
        "inverter_count": 10,
    })
    diagram["nodes"].append(_node(
        "s2", "station", mode="catalogue", model="SUNGROW_MVS3200",
        pv_inverter="sungrow-sg350hx-20", inverter_count=10,
    ))
    diagram["edges"].append(_edge("e_t2", "s1", "s2", length_m=400.0))

    result = solve_diagram(diagram, db)

    assert result["issues"] == []
    assert result["results"] is not None
    nodes = result["results"]["nodes"]
    assert nodes["s1"]["i_a"] < 630.0  # each station's OWN current is fine on its own
    assert nodes["s2"]["i_a"] < 630.0
    warnings = result["results"]["warnings"]
    matches = [w for w in warnings if w["code"] == "switchgear_through_current_exceeded"]
    assert len(matches) == 1
    assert matches[0]["node_id"] == "s1"  # nearest the busbar, carries the most
    assert "642" in matches[0]["message"] or "630" in matches[0]["message"]


def test_station_over_own_switchgear_rating_on_its_own_current_is_an_engine_error():
    # A single station whose OWN current alone (no downstream) already exceeds
    # its OWN switchgear rated current is a hard error: the catalogue is
    # self-contradictory and nothing downstream of it is trustworthy, in the
    # same style as the existing "No cable can carry" error.
    diagram = _minimal()
    diagram["nodes"][0]["props"].update({"p_target_mw": 25.0, "pf": 0.95})
    diagram["nodes"][2]["props"].update({
        "model": "SUNGROW_MVS3200",
        "pv_inverter": "sungrow-sg350hx-20",
        "inverter_count": 10,
    })

    result = solve_diagram(diagram, db)

    assert result["results"] is None
    assert result["issues"][0]["code"] == "engine_error"
    message = result["issues"][0]["message"]
    assert "738" in message and "630" in message
    assert "switchgear rated current" in message


def test_inverter_apparent_limit_is_independent_of_active_and_transformer_limits():
    diagram = _minimal()
    diagram["settings"]["rules"]["max_loading_pv"] = 1.10
    diagram["nodes"][0]["props"].update({"p_target_mw": 2.4, "pf": 0.8})
    diagram["nodes"][2]["props"].update({
        "model": "SUNGROW_MVS3200",
        "pv_inverter": "sungrow-sg350hx-20",
        "inverter_count": 10,
    })

    result = solve_diagram(diagram, db)

    station = result["results"]["nodes"]["s1"]
    codes = {warning["code"] for warning in result["results"]["warnings"]}
    assert station["inverter_active_ok"] is True
    assert station["inverter_apparent_ok"] is False
    assert "inverter_active_capacity_exceeded" not in codes
    assert "inverter_apparent_capacity_exceeded" in codes
    assert "fleet_overloaded" not in codes


def test_missing_30c_inverter_power_falls_back_to_40c_with_notice():
    inverter_key = "sungrow-sg350hx-20"
    inverter = replace(db.pv_inverters[inverter_key], power_kw_at_30c=None)
    fallback_db = ComponentDatabase(
        cables=db.cables,
        transformers=db.transformers,
        bess_solutions=db.bess_solutions,
        bess_transformers=db.bess_transformers,
        bess_pairings=db.bess_pairings,
        pv_inverters={**db.pv_inverters, inverter_key: inverter},
        pv_inverter_pairings=db.pv_inverter_pairings,
    )
    diagram = _minimal()
    diagram["settings"]["rules"]["ambient_temp_c"] = 30
    diagram["nodes"][2]["props"].update({
        "model": "SUNGROW_MVS3200",
        "pv_inverter": inverter_key,
        "inverter_count": 10,
    })

    result = solve_diagram(diagram, fallback_db)

    assert result["issues"] == []
    station = result["results"]["nodes"]["s1"]
    assert station["inverter_unit_power_kw"] == 320
    assert any(
        warning["code"] == "inverter_ambient_power_not_published"
        and warning["node_id"] == "s1"
        for warning in result["results"]["warnings"]
    )


def test_single_fleet_refinement_reselects_cable_after_pq_threshold_crossing():
    diagram = _minimal()
    diagram["nodes"][0]["props"]["p_target_mw"] = 6.0
    result = client.post("/api/solve", json=diagram).json()
    assert result["issues"] == []
    cable = result["results"]["edges"]["e_t1"]
    # The initial active-only pass fits AL_95; converged P/Q flow requires the
    # next catalogue size, proving the final selection was revalidated.
    assert cable["cable_label"] == "Al_3x1x120_20kV"
    assert cable["current_a"] == pytest.approx(
        cable["s_kva"] / (math.sqrt(3.0) * 20.0))


def test_unknown_keys_are_ignored():
    # Permissive parsing: the canvas carries cosmetic fields the engine never
    # reads, and the schema will grow. Unknown keys must not fail a drawing.
    diagram = _minimal()
    diagram["viewport"] = {"zoom": 1.4}
    diagram["nodes"][0]["selected"] = True
    diagram["nodes"][0]["props"]["colour"] = "red"
    diagram["edges"][0]["animated"] = True
    assert validate_graph(diagram, db) == []


def test_saved_max_circuit_current_a_rule_is_ignored_not_read():
    # ADR-0006 retired the flat 400 A planning cap outright — a design saved
    # before the retirement may still carry the key in settings.rules, and it
    # must be ignored (never fail, never change a number), same as any other
    # unknown rule key: solve to the byte-identical result with or without it.
    with_stray_key = _hv_diagram()
    with_stray_key["settings"]["rules"]["max_circuit_current_a"] = 50.0
    without = _hv_diagram()

    with_result = solve_diagram(with_stray_key, db)
    without_result = solve_diagram(without, db)
    assert with_result["issues"] == without_result["issues"] == []
    assert with_result == without_result


def test_no_poc():
    diagram = _minimal()
    diagram["nodes"] = [n for n in diagram["nodes"] if n["kind"] != "poc"]
    diagram["edges"] = [e for e in diagram["edges"] if e["id"] != "e_poc"]
    assert "no_poc" in _codes(validate_graph(diagram, db))


def test_multiple_poc():
    diagram = _minimal()
    diagram["nodes"].append(_node("poc2", "poc", p_target_mw=3.0, pf=0.95))
    diagram["edges"].append(_edge("e_poc2", "poc2", "bus", length_m=0.0))
    issues = validate_graph(diagram, db)
    assert "multiple_poc" in _codes(issues)
    assert any(i.node_id == "poc2" for i in issues if i.code == "multiple_poc")


def test_cycle():
    # A second cable back to the busbar closes a ring: MV circuits are radial.
    diagram = _minimal()
    diagram["nodes"].append(
        _node("s2", "station", mode="catalogue", model="HUAWEI_JUPITER3000"))
    diagram["edges"].append(_edge("e_t2", "s1", "s2", length_m=350.0))
    diagram["edges"].append(_edge("e_ring", "s2", "bus", length_m=350.0))
    issues = validate_graph(diagram, db)
    assert "cycle" in _codes(issues)
    # The offending edge is whichever one closed the loop on the walk — either
    # cable of the ring is a valid one to point the user at.
    assert {i.edge_id for i in issues if i.code == "cycle"} <= {"e_t2", "e_ring"}
    assert [i.edge_id for i in issues if i.code == "cycle"] != [None]


def test_disconnected():
    diagram = _minimal()
    diagram["nodes"].append(
        _node("orphan", "station", mode="catalogue", model="HUAWEI_JUPITER3000"))
    issues = validate_graph(diagram, db)
    assert "disconnected" in _codes(issues)
    assert [i.node_id for i in issues if i.code == "disconnected"] == ["orphan"]


def test_station_degree():
    # One cable in, at most one out: a station feeding two stations is a branch,
    # not a daisy chain.
    diagram = _minimal()
    for name in ("s2", "s3"):
        diagram["nodes"].append(
            _node(name, "station", mode="catalogue", model="HUAWEI_JUPITER3000"))
        diagram["edges"].append(_edge(f"e_{name}", "s1", name, length_m=350.0))
    issues = validate_graph(diagram, db)
    assert "station_degree" in _codes(issues)
    assert any(i.node_id == "s1" for i in issues if i.code == "station_degree")


def test_missing_length():
    diagram = _minimal()
    del diagram["edges"][1]["length_m"]
    issues = validate_graph(diagram, db)
    assert "missing_length" in _codes(issues)
    assert any(i.edge_id == "e_t1" for i in issues)

    zero = _minimal()
    zero["edges"][1]["length_m"] = 0.0
    assert "missing_length" in _codes(validate_graph(zero, db))


def test_unknown_model():
    diagram = _minimal()
    diagram["nodes"][2]["props"]["model"] = "NOT_A_TRANSFORMER"
    issues = validate_graph(diagram, db)
    assert "unknown_model" in _codes(issues)
    assert any(i.node_id == "s1" for i in issues if i.code == "unknown_model")

    no_model = _minimal()
    no_model["nodes"][2]["props"] = {}
    assert "unknown_model" in _codes(validate_graph(no_model, db))


def test_bad_tier():
    # The trunk drawn as an HV line: tiers carry the voltages, so a mismatched
    # tier would silently size the run at the wrong voltage.
    diagram = _minimal()
    diagram["edges"][1]["tier"] = "hv"
    issues = validate_graph(diagram, db)
    assert "bad_tier" in _codes(issues)
    assert any(i.edge_id == "e_t1" for i in issues if i.code == "bad_tier")

    unknown = _minimal()
    unknown["edges"][1]["tier"] = "ehv"
    assert "bad_tier" in _codes(validate_graph(unknown, db))

    # An HV interconnection drawn without an hv_kv in the settings.
    no_hv = _hv_diagram()
    no_hv["settings"]["tiers"]["hv_kv"] = None
    assert "bad_tier" in _codes(validate_graph(no_hv, db))


def test_unknown_and_mismatched_forced_cable():
    diagram = _minimal()
    diagram["edges"][1]["sizing"] = {"mode": "forced", "cable": "NOPE"}
    assert "unknown_cable" in _codes(validate_graph(diagram, db))

    lv_cable = next(c.name for c in db.cables.values() if c.rated_voltage_kv == 1.0)
    mismatched = _minimal()
    mismatched["edges"][1]["sizing"] = {"mode": "forced", "cable": lv_cable}
    assert "bad_tier" in _codes(validate_graph(mismatched, db))


def test_bad_topology_and_schema():
    # An aux load hung off a station instead of the busbar.
    diagram = _minimal()
    diagram["edges"][2] = _edge("e_aux", "s1", "aux")
    assert "bad_topology" in _codes(validate_graph(diagram, db))

    # A block of an unknown kind, and an edge to nowhere.
    broken = _minimal()
    broken["nodes"].append({"id": "x", "kind": "inverter", "props": {}})
    broken["edges"].append(_edge("e_x", "bus", "ghost"))
    codes = _codes(validate_graph(broken, db))
    assert "bad_schema" in codes and "unknown_node" in codes


def test_bad_props():
    diagram = _minimal()
    diagram["nodes"][0]["props"] = {"p_target_mw": 0.0, "pf": 1.5}
    assert "bad_props" in _codes(validate_graph(diagram, db))


def test_custom_station_transformer_accepted_and_checked():
    diagram = _minimal()
    diagram["nodes"][2]["props"] = {
        "mode": "custom", "name": "Custom 3 MVA", "s_rated_kva": 3000.0,
        "uk_percent": 6.0, "pk_kw": 30.0, "p0_kw": 3.0, "i0_percent": 0.5,
        "custom_inverter_name": "Custom 3 MW", "custom_inverter_power_kw_at_40c": 3000.0,
        "custom_inverter_nominal_ac_voltage_kv": 0.8, "inverter_count": 1,
    }
    assert validate_graph(diagram, db) == []
    inputs = graph_to_inputs(diagram, db)
    assert inputs.branches[0].circuits[0][0].s_rated_kva_at_40c == 3000.0

    # uk% below the resistive share implied by Pk: the loss model rejects it.
    diagram["nodes"][2]["props"]["uk_percent"] = 0.5
    assert "bad_props" in _codes(validate_graph(diagram, db))


def test_custom_pv_inverter_uses_40c_fallback_and_does_not_validate_voltage():
    diagram = _minimal()
    diagram["settings"]["rules"]["ambient_temp_c"] = 30
    diagram["nodes"][0]["props"].update({"p_target_mw": 1.0, "pf": 0.95})
    diagram["nodes"][2]["props"] = {
        "mode": "custom",
        "fleet_kind": "pv",
        "name": "One-off station",
        "s_rated_kva": 3000.0,
        "uk_percent": 6.0,
        "pk_kw": 30.0,
        "custom_inverter_name": "Prototype 500",
        "custom_inverter_power_kw_at_40c": 500.0,
        # Deliberately different from the diagram LV tier. Voltage is recorded,
        # never treated as a compatibility gate.
        "custom_inverter_nominal_ac_voltage_kv": 0.4,
        "inverter_count": 3,
    }

    assert validate_graph(diagram, db) == []
    inputs = graph_to_inputs(diagram, db)
    installation = inputs.branches[0].pv_inverters_by_station["s1"]
    assert installation.inverter.nominal_ac_voltage_kv == 0.4
    assert installation.unit_capability.power_kw == 500.0
    assert installation.unit_capability.used_fallback is True

    result = solve_diagram(diagram, db)
    assert result["issues"] == []
    station = result["results"]["nodes"]["s1"]
    assert station["inverter_count"] == 3
    assert station["inverter_unit_power_kw"] == 500.0
    codes = {warning["code"] for warning in result["results"]["warnings"]}
    assert "inverter_ambient_power_not_published" in codes
    assert "inverter_minimum_power_factor_not_provided" in codes


def test_custom_inverter_minimum_power_factor_warning_calls_it_configured():
    diagram = _minimal()
    diagram["nodes"][0]["props"].update({"p_target_mw": 1.0, "pf": 0.7})
    diagram["nodes"][2]["props"] = {
        "mode": "custom",
        "fleet_kind": "pv",
        "name": "One-off station",
        "s_rated_kva": 3000.0,
        "uk_percent": 6.0,
        "pk_kw": 30.0,
        "custom_inverter_name": "Prototype 2 MW",
        "custom_inverter_power_kw_at_40c": 2000.0,
        "custom_inverter_nominal_ac_voltage_kv": 0.8,
        "custom_inverter_minimum_power_factor": 0.8,
        "inverter_count": 1,
    }

    result = solve_diagram(diagram, db)
    warning = next(
        item for item in result["results"]["warnings"]
        if item["code"] == "inverter_power_factor_below_minimum"
    )
    assert "configured minimum" in warning["message"]
    assert "published minimum" not in warning["message"]


@pytest.mark.parametrize(
    "patch",
    [
        {"custom_inverter_name": ""},
        {"custom_inverter_power_kw_at_40c": 0},
        {"custom_inverter_nominal_ac_voltage_kv": 0},
        {"inverter_count": 0},
        {"inverter_count": 1.5},
        {"custom_inverter_power_kw_at_30c": 0},
        {"custom_inverter_minimum_power_factor": 1.1},
    ],
)
def test_custom_pv_inverter_rejects_incomplete_or_invalid_values(patch):
    diagram = _minimal()
    props = {
        "mode": "custom",
        "fleet_kind": "pv",
        "name": "One-off station",
        "s_rated_kva": 3000.0,
        "uk_percent": 6.0,
        "pk_kw": 30.0,
        "custom_inverter_name": "Prototype 500",
        "custom_inverter_power_kw_at_40c": 500.0,
        "custom_inverter_nominal_ac_voltage_kv": 0.8,
        "inverter_count": 3,
    }
    props.update(patch)
    diagram["nodes"][2]["props"] = props

    assert "bad_custom_pv_inverter" in _codes(validate_graph(diagram, db))


def test_bess_station_without_solution_is_rejected():
    diagram = _minimal()
    diagram["nodes"][2]["props"] = {
        "mode": "catalogue", "model": "GENERIC_BESS_TX_2750_LV069", "fleet_kind": "bess",
    }
    issues = validate_graph(diagram, db)
    assert "unknown_bess_solution" in _codes(issues)
    assert any(i.node_id == "s1" for i in issues if i.code == "unknown_bess_solution")


def test_bess_station_lv_mismatch_is_rejected():
    diagram = _minimal()
    diagram["nodes"][2]["props"] = {
        # GENERIC_BESS_TX_1750_LV100 is 1.0 kV; sungrow-st6900ux-4h's PCS is
        # 0.69 kV.
        "mode": "catalogue", "model": "GENERIC_BESS_TX_1750_LV100", "fleet_kind": "bess",
        "bess_solution": "sungrow-st6900ux-4h",
    }
    issues = validate_graph(diagram, db)
    assert "bess_lv_mismatch" in _codes(issues)
    assert any(i.node_id == "s1" for i in issues if i.code == "bess_lv_mismatch")


# --- ticket 02: the pairing lives on the station transformer ---------------

def _bess_station_props(model="GENERIC_BESS_TX_2750_LV069",
                        solution="sungrow-st6900ux-4h", **extra):
    return {"mode": "catalogue", "model": model, "fleet_kind": "bess",
            "bess_solution": solution, **extra}


def test_a_paired_combination_validates_clean():
    diagram = _minimal()
    diagram["nodes"][2]["props"] = _bess_station_props()
    assert "unpaired_bess_solution" not in _codes(validate_graph(diagram, db))


def test_an_unpaired_solution_and_station_transformer_is_rejected():
    # GENERIC_BESS_TX_1750_LV100 carries no paired_solutions at all.
    diagram = _minimal()
    diagram["nodes"][2]["props"] = _bess_station_props(model="GENERIC_BESS_TX_1750_LV100")
    issues = validate_graph(diagram, db)
    assert "unpaired_bess_solution" in _codes(issues)
    assert any(i.node_id == "s1" for i in issues if i.code == "unpaired_bess_solution")


def test_a_custom_station_transformer_is_exempt_from_the_pairing_check():
    # A custom, hand-typed transformer corresponds to no catalogue entry, so
    # there is no supplier pairing to check it against — sizing behaviour for
    # a custom BESS station does not change in this ticket.
    diagram = _minimal()
    diagram["nodes"][2]["props"] = {
        "mode": "custom", "name": "Custom station", "s_rated_kva": 3000.0,
        "uk_percent": 6.0, "pk_kw": 30.0, "fleet_kind": "bess",
        "bess_solution": "sungrow-st6900ux-4h",
    }
    assert "unpaired_bess_solution" not in _codes(validate_graph(diagram, db))


def test_supported_durations_is_transformer_driven():
    # GENERIC_BESS_TX_2750_LV069 is paired with sungrow-st6900ux-4h (4 h) only.
    diagram = _minimal()
    diagram["nodes"][2]["props"] = _bess_station_props()
    from powertool.graph import _parse_structure
    parsed_nodes, _ = _parse_structure(diagram, [])
    assert supported_durations(parsed_nodes, db) == [4.0]


def test_supported_durations_is_empty_for_an_unpaired_transformer():
    diagram = _minimal()
    diagram["nodes"][2]["props"] = _bess_station_props(model="GENERIC_BESS_TX_1750_LV100")
    from powertool.graph import _parse_structure
    parsed_nodes, _ = _parse_structure(diagram, [])
    assert supported_durations(parsed_nodes, db) == []


def test_the_0_5c_and_1c_station_transformers_offer_different_durations():
    # This is the behaviour the whole 0.5 C distinction exists for: the
    # MVS7080-LS is paired only with the 2 h solution, the MVS7400-LS only
    # with the 4 h solution.
    from powertool.graph import _parse_structure

    diagram = _minimal()
    diagram["nodes"][2]["props"] = _bess_station_props(
        model="SUNGROW_MVS7080_LS", solution="sungrow-st6680ux-2h")
    parsed_nodes, _ = _parse_structure(diagram, [])
    assert supported_durations(parsed_nodes, db) == [2.0]

    diagram = _minimal()
    diagram["nodes"][2]["props"] = _bess_station_props(
        model="SUNGROW_MVS7400_LS", solution="sungrow-st6900ux-4h")
    parsed_nodes, _ = _parse_structure(diagram, [])
    assert supported_durations(parsed_nodes, db) == [4.0]


def test_mixing_the_0_5c_and_1c_stations_has_no_common_duration():
    # supported_durations is documented to return empty when two drawn
    # stations' transformers share no duration in common.
    from powertool.graph import _parse_structure

    diagram = _minimal()
    diagram["nodes"][2]["props"] = _bess_station_props(
        model="SUNGROW_MVS7080_LS", solution="sungrow-st6680ux-2h")
    diagram["nodes"].append(_node(
        "s2", "station", mode="catalogue", model="SUNGROW_MVS7400_LS",
        fleet_kind="bess", bess_solution="sungrow-st6900ux-4h"))
    parsed_nodes, _ = _parse_structure(diagram, [])
    assert supported_durations(parsed_nodes, db) == []


def test_container_count_defaults_from_the_pairing():
    diagram = _minimal()
    diagram["settings"]["tiers"]["lv_kv"] = 0.69
    diagram["nodes"][1]["props"]["fleet_kind"] = "bess"
    diagram["nodes"][2]["props"] = _bess_station_props()
    diagram["settings"]["rules"]["discharge_hours"] = 4.0
    assert validate_graph(diagram, db) == []
    branch = graph_to_inputs(diagram, db).branches[0]
    assert branch.containers_by_station == {"s1": 1}
    assert branch.containers == 1
    assert branch.e_delivered_kwh == 6904.0


def test_container_count_override_wins_over_the_pairing_default():
    diagram = _minimal()
    diagram["settings"]["tiers"]["lv_kv"] = 0.69
    diagram["nodes"][1]["props"]["fleet_kind"] = "bess"
    diagram["nodes"][2]["props"] = _bess_station_props(
        model="GENERIC_BESS_TX_4000_LV069", containers_override=1)
    diagram["settings"]["rules"]["discharge_hours"] = 4.0
    assert validate_graph(diagram, db) == []
    branch = graph_to_inputs(diagram, db).branches[0]
    # The pairing default for this station transformer is 2 containers; the
    # override reads 1 instead, and the delivered energy follows it.
    assert branch.containers_by_station == {"s1": 1}
    assert branch.e_delivered_kwh == 6904.0


@pytest.mark.parametrize("bad_override", [0, -1, 2.5, "3"])
def test_a_bad_containers_override_is_rejected(bad_override):
    diagram = _minimal()
    diagram["nodes"][2]["props"] = _bess_station_props(containers_override=bad_override)
    issues = validate_graph(diagram, db)
    assert "bad_props" in _codes(issues)
    assert any(i.node_id == "s1" for i in issues if i.code == "bad_props")


def test_bess_single_fleet_design_validates_and_solves_like_pv():
    # A discharging battery is modelled as a generator: with an identical
    # transformer, a BESS station must size to exactly the same numbers a PV
    # station would — sizing behaviour does not change in this ticket.
    identical_tx = {
        "mode": "custom", "name": "Identical station", "s_rated_kva": 3000.0,
        "uk_percent": 6.0, "pk_kw": 30.0, "p0_kw": 3.0, "i0_percent": 0.5,
        "custom_inverter_name": "Identical inverter",
        "custom_inverter_power_kw_at_40c": 3000.0,
        "custom_inverter_nominal_ac_voltage_kv": 0.69,
        "inverter_count": 1,
    }

    pv = _minimal()
    pv["settings"]["tiers"]["lv_kv"] = 0.69
    pv["nodes"][2]["props"] = dict(identical_tx)
    assert validate_graph(pv, db) == []
    pv_result = client.post("/api/solve", json=pv).json()
    assert pv_result["issues"] == []

    bess = _minimal()
    bess["settings"]["tiers"]["lv_kv"] = 0.69
    bess["nodes"][2]["props"] = {
        **identical_tx, "fleet_kind": "bess", "bess_solution": "sungrow-st6900ux-4h",
    }
    assert validate_graph(bess, db) == []
    bess_result = client.post("/api/solve", json=bess).json()
    assert bess_result["issues"] == []

    # The fleet kind is a label on identical CONVERSION physics: the PCS sizes
    # exactly as the inverter does. Two things legitimately differ, and both are
    # deliberate rather than drift:
    #   - fleet_kind itself, dead when this test was written (ticket 02 added
    #     the field, ticket 05 wired it);
    #   - everything downstream of the busbar, because ticket 07 attaches the
    #     BESS solution's worst-case auxiliary draw there.
    bess_station = dict(bess_result["results"]["nodes"]["s1"])
    pv_station = dict(pv_result["results"]["nodes"]["s1"])
    assert bess_station.pop("fleet_kind") == "bess"
    assert pv_station.pop("fleet_kind") == "pv"
    # PV additionally reports the custom inverter's independent compliance;
    # remove those presentation-only fields before comparing shared station
    # conversion physics with the BESS result.
    for key in [key for key in pv_station if key.startswith("inverter_")]:
        pv_station.pop(key)
    assert bess_station == pv_station

    # Every sized number still matches, including after ticket 07 gave BESS
    # solutions an auxiliary draw: that draw is fed from a separate supply, so
    # it never enters the sizing cascade. The branch summary reports it (see
    # tests/test_hybrid.py) without sizing anything against it.
    bess_summary = dict(bess_result["results"]["summary"])
    pv_summary = dict(pv_result["results"]["summary"])
    assert bess_summary.pop("branches") != pv_summary.pop("branches")  # fleet kind, aux
    assert bess_summary == pv_summary


# --- graph_to_inputs: the positional bijection ------------------------------

def _hv_diagram() -> dict:
    """Two circuits behind an HV interconnection, drawn small-circuit-first."""
    diagram = {
        "schema_version": 1,
        "settings": _settings(hv_kv=132.0),
        "nodes": [
            _node("poc", "poc", p_target_mw=20.0, pf=0.95),
            _node("hv", "hv_tx", mode="auto", n_parallel=1),
            _node("bus", "busbar"),
            _node("a1", "station", mode="catalogue", model="HUAWEI_JUPITER3000",
                  pv_inverter="huawei-sun2000-330ktl-h1", inverter_count=11),
            _node("b1", "station", mode="catalogue", model="HUAWEI_JUPITER9000",
                  pv_inverter="huawei-sun2000-330ktl-h1", inverter_count=30),
            _node("b2", "station", mode="catalogue", model="HUAWEI_JUPITER3000",
                  pv_inverter="huawei-sun2000-330ktl-h1", inverter_count=11),
            _node("aux", "aux", p_kw=120.0, q_kvar=40.0),
        ],
        "edges": [
            _edge("e_exp", "poc", "hv", tier="hv", length_m=1500.0),
            _edge("e_sub", "hv", "bus"),
            _edge("e_a1", "bus", "a1", length_m=900.0),
            _edge("e_b1", "bus", "b1", length_m=700.0),
            _edge("e_b2", "b1", "b2", length_m=250.0),
            _edge("e_aux", "bus", "aux"),
        ],
    }
    return diagram


def test_graph_to_inputs_round_trip_is_positional():
    diagram = _hv_diagram()
    assert validate_graph(diagram, db) == []
    inputs = graph_to_inputs(diagram, db)

    # Circuits follow the drawing's own edge order; stations follow the chain
    # outward from the busbar. Nothing is sorted or regrouped.
    branch = inputs.branches[0]
    assert branch.station_ids == [["a1"], ["b1", "b2"]]
    assert [[tx.s_rated_kva_at_40c for tx in c] for c in branch.circuits] == \
           [[3300], [9000, 3300]]
    assert branch.segment_edge_ids == {
        (1, 1): "e_a1", (2, 1): "e_b1", (2, 2): "e_b2"}
    assert branch.segment_lengths == {(1, 1): 0.9, (2, 1): 0.7, (2, 2): 0.25}
    assert len(branch.segment_lengths) == branch.n_stations  # complete map

    assert inputs.p_poc_kw == 20_000.0 and inputs.pf_target == 0.95
    assert inputs.v_mv_kv == 20.0 and inputs.v_hv_kv == 132.0
    assert inputs.hv_mode == "auto" and inputs.hv_transformer is None
    assert inputs.export_edge_id == "e_exp" and inputs.export_length_km == 1.5
    assert branch.aux_ids == ["aux"]
    assert (branch.aux_p_kw, branch.aux_q_kvar) == (120.0, 40.0)
    assert branch.fleet == [(db.transformer("HUAWEI_JUPITER3000"), 2),
                            (db.transformer("HUAWEI_JUPITER9000"), 1)]


def test_forced_section_reaches_the_engine_inputs():
    diagram = _hv_diagram()
    diagram["edges"][3]["sizing"] = {"mode": "forced", "cable": "AL_400_20kV"}
    assert validate_graph(diagram, db) == []
    inputs = graph_to_inputs(diagram, db)
    branch = inputs.branches[0]
    assert [c.name for c in branch.segment_candidates[(2, 1)]] == ["AL_400_20kV"]
    assert list(branch.segment_candidates) == [(2, 1)]  # only the pinned run


def test_map_results_keys_every_drawn_element():
    from backend.solve import solve_architecture

    diagram = _hv_diagram()
    inputs = graph_to_inputs(diagram, db)
    stage1, layout, arch = solve_architecture(inputs, db)
    results = map_results(inputs, stage1, arch)

    assert set(results["edges"]) == {"e_a1", "e_b1", "e_b2", "e_exp"}
    assert set(results["nodes"]) == {"poc", "hv", "bus", "a1", "b1", "b2", "aux"}
    assert results["nodes"]["b2"]["circuit"] == 2
    assert results["nodes"]["b2"]["position"] == 2
    assert results["nodes"]["b1"]["model"] == "9000 kVA - Huawei"
    assert results["edges"]["e_b2"]["length_m"] == 250.0
    assert results["edges"]["e_b1"]["s_kva"] > results["edges"]["e_b2"]["s_kva"]
    assert results["summary"]["n_circuits"] == 2
    assert results["summary"]["circuit_sizes"] == [1, 2]
    assert results["summary"]["power_balance_ok"]
    # No 132 kV cables in the catalogue yet: the export span is reported unsized.
    assert results["edges"]["e_exp"]["sized"] is False
    assert any(w["code"] == "hv_cable_not_sized" for w in results["warnings"])


def test_absent_ambient_setting_behaves_as_40c():
    # No settings.rules.ambient_temp_c at all — every design saved before this
    # setting existed — must resolve exactly the 40C figure it always did.
    diagram = _minimal()
    assert "ambient_temp_c" not in diagram["settings"]["rules"]
    inputs = graph_to_inputs(diagram, db)
    assert inputs.ambient_c == 40.0

    from backend.solve import solve_diagram
    result = solve_diagram(diagram, db)
    assert result["issues"] == []
    assert not any(w["code"] == "ambient_rating_not_published" for w in result["results"]["warnings"])
    tx = db.transformer("HUAWEI_JUPITER3000")
    assert result["results"]["nodes"]["s1"]["s_rated_kva"] == tx.s_rated_kva_at_40c


def test_ambient_30_falls_back_to_40_with_a_warning_and_still_solves():
    # HUAWEI_JUPITER3000 (the station _minimal() draws) publishes no 30C
    # figure — a design asking for 30C must still solve, using the nearest
    # published ambient at or above it (40C), with a warning naming the gap.
    diagram = _minimal()
    diagram["settings"]["rules"]["ambient_temp_c"] = 30
    assert validate_graph(diagram, db) == []  # a warning, not a blocking issue
    inputs = graph_to_inputs(diagram, db)
    assert inputs.ambient_c == 30.0

    from backend.solve import solve_diagram
    result = solve_diagram(diagram, db)
    assert result["issues"] == []
    warnings = result["results"]["warnings"]
    assert any(w["code"] == "ambient_rating_not_published" for w in warnings)
    tx = db.transformer("HUAWEI_JUPITER3000")
    assert tx.s_rated_kva_at_30c is None  # the entry this fallback exercises
    assert result["results"]["nodes"]["s1"]["s_rated_kva"] == tx.s_rated_kva_at_40c


def test_mv_interconnection_sizes_the_drawn_export_run():
    # No MV/HV transformer: the POC -> busbar cable IS the export run, sized at
    # the MV voltage with its drawn length and the export %/km budget.
    diagram = _minimal()
    diagram["nodes"][0]["props"]["p_target_mw"] = 6.0
    diagram["edges"][0]["length_m"] = 2500.0
    diagram["nodes"].append(
        _node("s2", "station", mode="catalogue", model="HUAWEI_JUPITER3000",
              pv_inverter="huawei-sun2000-330ktl-h1", inverter_count=11))
    diagram["edges"].append(_edge("e_t2", "s1", "s2", length_m=400.0))
    assert validate_graph(diagram, db) == []

    inputs = graph_to_inputs(diagram, db)
    assert inputs.hv_mode == "none" and inputs.v_hv_kv is None
    assert inputs.export_length_km == 2.5

    results = client.post("/api/solve", json=diagram).json()["results"]
    export = results["edges"]["e_poc"]
    assert export["sized"] and export["length_m"] == 2500.0
    assert export["dp_kw"] > 0
    assert results["summary"]["v_hv_kv"] == 20.0  # export at the MV voltage
    assert "hv" not in results["nodes"]


def _hybrid_mv_export_diagram() -> dict:
    diagram = _minimal()
    diagram["nodes"][0]["props"]["p_target_bess_mw"] = 2.0
    diagram["nodes"][1]["props"]["fleet_kind"] = "pv"
    diagram["nodes"] = [node for node in diagram["nodes"] if node["id"] != "aux"]
    diagram["edges"] = [edge for edge in diagram["edges"] if edge["id"] != "e_aux"]
    diagram["edges"][0]["id"] = "e_poc_pv"
    diagram["edges"][0]["length_m"] = 500.0
    diagram["nodes"] += [
        _node("bus_b", "busbar", fleet_kind="bess"),
        _node("s_b1", "station", mode="catalogue",
              model="GENERIC_BESS_TX_2750_LV069", fleet_kind="bess",
              bess_solution="sungrow-st6900ux-4h"),
    ]
    diagram["edges"] += [
        _edge("e_poc_bess", "poc", "bus_b", length_m=2500.0),
        _edge("e_tb1", "bus_b", "s_b1", length_m=600.0),
    ]
    return diagram


def test_hybrid_mv_interconnection_sizes_and_maps_each_direct_export_run():
    """Each fleet's direct POC-to-busbar run is an independent MV export."""
    diagram = _hybrid_mv_export_diagram()

    assert validate_graph(diagram, db) == []
    body = client.post("/api/solve", json=diagram).json()

    assert body["issues"] == []
    exports = body["results"]["edges"]
    assert exports["e_poc_pv"]["length_m"] == 500.0
    assert exports["e_poc_pv"]["dp_kw"] > 0
    assert exports["e_poc_bess"]["length_m"] == 2500.0
    assert exports["e_poc_bess"]["dp_kw"] > exports["e_poc_pv"]["dp_kw"]
    assert body["results"]["summary"]["power_balance_ok"] is True
    assert body["results"]["summary"]["v_hv_kv"] == 20.0
    assert body["results"]["summary"]["total_cable_loss_kw"] == pytest.approx(
        sum(edge["dp_kw"] for edge in exports.values()))
    nodes = body["results"]["nodes"]
    station_input = sum(node["p_lv_kw"] for node in nodes.values()
                        if node.get("kind") == "station")
    transformer_loss = sum(node["dp_tx_kw"] for node in nodes.values()
                           if node.get("kind") == "station")
    assert station_input == pytest.approx(
        body["results"]["summary"]["p_poc_delivered_kw"]
        + transformer_loss + body["results"]["summary"]["total_cable_loss_kw"])


def test_hybrid_mv_export_results_do_not_depend_on_poc_edge_order():
    first = client.post("/api/solve", json=_hybrid_mv_export_diagram()).json()
    reversed_diagram = _hybrid_mv_export_diagram()
    reversed_diagram["edges"] = [reversed_diagram["edges"][2],
                                  reversed_diagram["edges"][1],
                                  reversed_diagram["edges"][0],
                                  reversed_diagram["edges"][3]]
    second = client.post("/api/solve", json=reversed_diagram).json()
    assert first["issues"] == second["issues"] == []
    for edge_id in ("e_poc_pv", "e_poc_bess"):
        assert second["results"]["edges"][edge_id] == first["results"]["edges"][edge_id]


def test_forced_hybrid_mv_export_maps_and_revalidates_its_drawn_run():
    diagram = _hybrid_mv_export_diagram()
    bess_edge = next(edge for edge in diagram["edges"] if edge["id"] == "e_poc_bess")
    bess_edge["sizing"] = {"mode": "forced", "cable": "AL_400_20kV"}
    body = client.post("/api/solve", json=diagram).json()
    assert body["issues"] == []
    export = body["results"]["edges"]["e_poc_bess"]
    assert export["forced"] is True
    assert export["cable"] == "AL_400_20kV"
    assert export["sized"] is True


def test_forced_hybrid_mv_export_that_cannot_carry_is_an_engine_error():
    diagram = _hybrid_mv_export_diagram()
    diagram["settings"]["rules"]["export_loss_pct_per_km"] = 0.0001
    bess_edge = next(edge for edge in diagram["edges"] if edge["id"] == "e_poc_bess")
    bess_edge["sizing"] = {"mode": "forced", "cable": "AL_95_20kV"}
    body = client.post("/api/solve", json=diagram).json()
    assert body["results"] is None
    assert body["issues"][0]["code"] == "engine_error"
    assert "No cable can carry" in body["issues"][0]["message"]


# --- /api/solve -------------------------------------------------------------

def test_solve_returns_issues_with_http_200():
    diagram = _minimal()
    diagram["edges"][1]["length_m"] = -5.0
    resp = client.post("/api/solve", json=diagram)
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] is None
    assert body["issues"][0]["code"] == "missing_length"
    assert body["issues"][0]["edge_id"] == "e_t1"


def test_solve_turns_engine_errors_into_issues_not_500s():
    # A forced 95 mm² trunk cannot carry a 20 MW plant: select_cable raises, and
    # the API must answer with an issue, never a server error.
    diagram = _hv_diagram()
    diagram["settings"]["rules"]["max_utilization"] = 0.10
    diagram["edges"][3]["sizing"] = {"mode": "forced", "cable": "AL_95_20kV"}
    resp = client.post("/api/solve", json=diagram)
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] is None
    assert body["issues"][0]["code"] == "engine_error"
    assert "No cable can carry" in body["issues"][0]["message"]


# --- THE GOLDEN TEST --------------------------------------------------------
#
# The 45 MW example plant of the deleted Streamlit app (5x JUPITER9000 +
# 3x JUPITER3000, HV interconnection at 132 kV, 20 kV collection, 120 kW /
# 40 kvar aux, POC 45 MW at pf 0.95, trunk 800 m, spacing 350 m), drawn on the
# canvas with the arrangement today's arrange_plant produces, must solve to
# exactly the numbers of the auto path.

EXAMPLE_ELEMENTS = [
    {"type": "Cable section", "v_kv": 20.0, "label": "MV collector"},
    {"type": "Transformer", "component": "HUAWEI_JUPITER9000", "v_kv": 20.0,
     "n_parallel": 5, "label": "MV/LV stations (big)"},
    {"type": "Transformer", "component": "HUAWEI_JUPITER3000", "v_kv": 20.0,
     "n_parallel": 3, "label": "MV/LV stations (small)"},
    {"type": "Aux load", "v_kv": 20.0, "p_kw": 120.0, "q_kvar": 40.0,
     "label": "Substation aux"},
]
P_POC_KW = 45_000.0
PF_TARGET = 0.95
V_HV_KV = 132.0
V_MV_KV = 20.0
TRUNK_M = 800.0
SPACING_M = 350.0
AUX_P_KW, AUX_Q_KVAR = 120.0, 40.0


def _auto_reference():
    """The example plant solved the way it is solved today: Stage-1 chain ->
    arrange_plant -> size_architecture with the app's default run lengths."""
    chain = build_chain(EXAMPLE_ELEMENTS, db, interconnection="HV",
                        v_export_kv=V_HV_KV, export_m=0.0,
                        p_poc_kw=P_POC_KW, pf_target=PF_TARGET)
    stage1 = size_pv_inverters(chain, p_poc_kw=P_POC_KW, pf_target=PF_TARGET)
    fleet = [(db.transformer("HUAWEI_JUPITER9000"), 5),
             (db.transformer("HUAWEI_JUPITER3000"), 3)]
    layout = arrange_plant(stage1, fleet, max_loading=1.0,
                           trunk_length_km=TRUNK_M / 1000.0,
                           spacing_km=SPACING_M / 1000.0, v_mv_kv=V_MV_KV)
    lengths = {
        (c_idx, s_idx): (TRUNK_M if s_idx == 1 else SPACING_M) / 1000.0
        for c_idx, n in enumerate(layout.circuit_sizes, start=1)
        for s_idx in range(1, n + 1)
    }
    arch = size_architecture(
        layout, stage1, db.cables_for_voltage(V_MV_KV),
        max_utilization=0.80, max_loss_percent_base=1.30,
        segment_lengths=lengths, auto_hv=True,
        hv_cable_candidates=[], hv_cable_length_km=0.0, v_hv_kv=V_HV_KV,
        export_loss_percent_per_km=0.10,
        aux_p_kw=AUX_P_KW, aux_q_kvar=AUX_Q_KVAR, p_poc_target_kw=P_POC_KW,
        q_poc_target_kvar=P_POC_KW * math.tan(math.acos(PF_TARGET)),
    )
    return stage1, layout, arch


def _drawn_example(layout) -> tuple[dict, list[list[str]], dict]:
    """Draw the reference plant on the canvas: one column of stations per
    circuit, in the arrangement (and the order) arrange_plant produced.

    Returns the diagram plus the station ids and segment edge ids by position,
    so the assertions can walk the drawing and the engine result together.
    """
    key_of = {id(tx): key for key, tx in db.transformers.items()}
    nodes = [
        _node("poc", "poc", p_target_mw=P_POC_KW / 1000.0, pf=PF_TARGET),
        _node("hv", "hv_tx", mode="auto", n_parallel=1),
        _node("bus", "busbar"),
        _node("aux", "aux", p_kw=AUX_P_KW, q_kvar=AUX_Q_KVAR),
    ]
    edges = [
        # POC at the substation fence: no export run (0 m), as in the example.
        _edge("e_export", "poc", "hv", tier="hv", length_m=0.0),
        _edge("e_sub", "hv", "bus"),
        _edge("e_aux", "bus", "aux"),
    ]
    station_ids, edge_ids = [], {}
    for c_idx, circuit in enumerate(layout.circuit_plans, start=1):
        ids = []
        for s_idx, plan in enumerate(circuit, start=1):
            node_id = f"s{c_idx}_{s_idx}"
            edge_id = f"c{c_idx}_seg{s_idx}"
            nodes.append(_node(node_id, "station", mode="catalogue",
                               model=key_of[id(plan.transformer)],
                               pv_inverter="huawei-sun2000-330ktl-h1",
                               inverter_count=(30 if plan.transformer.s_rated_kva_at_40c == 9000 else 11),
                               x=float(c_idx), y=float(s_idx)))
            edges.append(_edge(edge_id, "bus" if s_idx == 1 else ids[-1], node_id,
                               length_m=TRUNK_M if s_idx == 1 else SPACING_M))
            ids.append(node_id)
            edge_ids[(c_idx, s_idx)] = edge_id
        station_ids.append(ids)
    diagram = {"schema_version": 1, "settings": _settings(hv_kv=V_HV_KV),
               "nodes": nodes, "edges": edges}
    return diagram, station_ids, edge_ids


def test_golden_45mw_example_drawn_equals_the_auto_path():
    stage1, layout, arch = _auto_reference()
    # Anchor the fixture: this is the arrangement the auto path produces today
    # (ADR-0006: each station's own 630 A fallback switchgear rating, not the
    # retired flat 400 A cap — a materially bigger bound, fewer circuits).
    assert layout.circuit_sizes == [4, 2, 2]
    assert [[p.transformer.s_rated_kva_at_40c for p in c] for c in layout.circuit_plans] == \
           [[9000, 3300, 3300, 3300], [9000, 9000], [9000, 9000]]

    diagram, station_ids, edge_ids = _drawn_example(layout)
    assert validate_graph(diagram, db) == []

    resp = client.post("/api/solve", json=diagram)
    assert resp.status_code == 200
    body = resp.json()
    assert body["issues"] == []
    results = body["results"]

    # Stage 1: the drawn diagram must imply the same conceptual chain.
    summary = results["summary"]
    assert summary["p_inv_kw"] == stage1.p_inv_kw
    assert summary["q_inv_kvar"] == stage1.q_inv_kvar
    assert summary["s_inv_kva"] == stage1.s_inv_kva

    # Stage 2: every plant-level figure, exactly.
    assert summary["circuit_sizes"] == layout.circuit_sizes
    assert summary["fleet_loading"] == pytest.approx(
        summary["s_inv_refined_kva"] / layout.s_fleet_kva)
    refinement = arch.branch_refinements[0]
    assert summary["p_poc_delivered_kw"] == arch.p_poc_delivered_kw
    assert summary["q_poc_delivered_kvar"] == arch.q_poc_delivered_kvar
    assert summary["correction_factor"] == refinement.correction_factor
    assert summary["s_inv_refined_kva"] == refinement.s_inv_refined_kva
    assert summary["p_poc_refined_delivered_kw"] == refinement.p_poc_refined_delivered_kw
    assert summary["total_cable_loss_kw"] == arch.total_cable_loss_kw
    assert summary["total_transformer_loss_kw"] == arch.total_transformer_loss_kw
    assert summary["worst_trunk_current_a"] == max(
        c.i_trunk_a for c in arch.branches[0].circuits)
    # The fixture draws Huawei stations, which publish no switchgear rated
    # current, so the ADR-0006 fallback notice is expected here. Nothing else is.
    assert summary["power_balance_ok"]
    assert [w["code"] for w in results["warnings"]] == ["switchgear_rating_not_published"]
    assert summary["p_poc_refined_delivered_kw"] >= P_POC_KW

    # Every cable run: same section, same losses, keyed to the drawn edge.
    for circuit in arch.branches[0].circuits:
        for segment in circuit.segments:
            drawn = results["edges"][edge_ids[(circuit.index, segment.index)]]
            assert drawn["cable_label"] == segment.cable_label
            assert drawn["n_parallel"] == segment.selection.n_parallel
            assert drawn["length_m"] == segment.length_km * 1000.0
            assert drawn["s_kva"] == segment.s_kva
            assert drawn["dp_kw"] == segment.dp_kw
            assert drawn["utilization"] == segment.selection.utilization
            assert drawn["current_a"] == segment.selection.current_per_circuit_a

    # Every station: same share, same loading, keyed to the drawn block.
    for circuit, ids in zip(arch.branches[0].circuits, station_ids):
        for station, node_id in zip(circuit.stations, ids):
            drawn = results["nodes"][node_id]
            assert drawn["model"] == station.model
            assert drawn["p_lv_kw"] == station.p_lv_kw
            assert drawn["dp_tx_kw"] == station.dp_tx_kw
            assert drawn["s_mv_kva"] == station.s_mv_kva
            assert drawn["loading"] == station.loading

    # The auto-sized MV/HV transformer, on the drawn block.
    assert results["nodes"]["hv"]["s_rated_kva"] == arch.export.hv_transformer.s_rated_kva_at_40c
    assert results["nodes"]["hv"]["dp_kw"] == arch.export.dp_tx_kw
    assert results["nodes"]["poc"]["p_target_kw"] == P_POC_KW
    assert math.isclose(results["nodes"]["bus"]["p_kw"],
                        sum(c.p_busbar_kw for c in arch.branches[0].circuits), rel_tol=1e-12)


def test_golden_rearranging_the_drawing_changes_the_numbers():
    # Sanity on the golden test: it compares real numbers, not a tautology —
    # moving one station to another circuit must move the losses.
    _stage1, layout, arch = _auto_reference()
    diagram, _ids, _edges = _drawn_example(layout)

    # Hang circuit 3's far 9 MVA station off the end of circuit 1's chain:
    # circuit 1 grows to 5 stations, circuit 3 shrinks to its lone remaining
    # one (still attached to the busbar), circuit 2 untouched.
    moved = {e["id"]: e for e in diagram["edges"]}
    moved["c3_seg2"]["source"] = "s1_4"
    resp = client.post("/api/solve", json=diagram)
    assert resp.status_code == 200
    body = resp.json()
    results = body["results"]
    assert body["issues"] == []
    assert results["summary"]["circuit_sizes"] == [5, 2, 1]
    assert results["summary"]["total_cable_loss_kw"] > arch.total_cable_loss_kw
    # ... and circuit 1's near station now carries more than its own 630 A
    # switchgear rated current in through current — flagged, never refused.
    through_current_warnings = [
        w for w in results["warnings"] if w["code"] == "switchgear_through_current_exceeded"]
    assert [w["node_id"] for w in through_current_warnings] == ["s1_1"]


def test_unrecognised_fleet_kind_is_rejected_not_coerced():
    # An ABSENT fleet kind means "pv" (see the backward-compatibility test).
    # A PRESENT but unrecognised one must be an issue: silently coercing
    # "BESS" to "pv" would validate the station against the PV catalogue and
    # size it as PV, with nothing anywhere saying so.
    for bad in ("BESS", "wind", "", 123):
        diagram = _minimal()
        diagram["nodes"][2]["props"]["fleet_kind"] = bad
        issues = validate_graph(diagram, db)
        assert "bad_fleet_kind" in _codes(issues), f"{bad!r} was accepted"
        assert any(i.node_id == "s1" for i in issues if i.code == "bad_fleet_kind")


# --- hybrid topology: one busbar per fleet kind (ticket 05) -----------------

def test_duplicate_busbar_is_rejected_and_named():
    # A second busbar of a kind that already exists is the relaxed rule's
    # narrower replacement for the old plant-wide multiple_busbar.
    diagram = _minimal()
    diagram["nodes"].append(_node("bus2", "busbar"))  # defaults to "pv", same as "bus"
    diagram["edges"].append(_edge("e_bus2", "poc", "bus2", length_m=0.0))
    issues = validate_graph(diagram, db)
    assert "duplicate_busbar" in _codes(issues)
    assert any(i.node_id == "bus2" for i in issues if i.code == "duplicate_busbar")
    # The old plant-wide code must not fire any more.
    assert "multiple_busbar" not in _codes(issues)


def test_busbar_kind_mismatch_is_rejected_and_named():
    # The busbar opts into a kind explicitly; s1 never heard of fleet_kind and
    # so reads as "pv" by the backward-compatibility fallback — disagreeing
    # with the busbar it hangs from.
    diagram = _minimal()
    diagram["nodes"][1]["props"]["fleet_kind"] = "bess"
    issues = validate_graph(diagram, db)
    assert "busbar_kind_mismatch" in _codes(issues)
    assert any(i.node_id == "s1" for i in issues if i.code == "busbar_kind_mismatch")


def test_a_lingering_q_share_pv_key_is_ignored():
    # Ticket 01: the user-controlled reactive split is gone, and with it the
    # bad_q_share issue. A diagram payload saved before the removal may still
    # carry the key (even a value that used to be out of range) — it is now
    # just another unknown key, parsed permissively and with no effect.
    diagram = _minimal()
    diagram["nodes"][0]["props"]["q_share_pv"] = 5.0  # would have been invalid
    assert validate_graph(diagram, db) == []
    plain = client.post("/api/solve", json=_minimal()).json()
    with_stale_key = client.post("/api/solve", json=diagram).json()
    assert with_stale_key["results"] == plain["results"]


def test_aux_load_on_a_second_busbar_validates():
    # A fully hybrid drawing — second busbar, own kind, own station, own aux
    # load — must validate cleanly: an aux load may hang from ANY busbar now,
    # not only "the" one.
    diagram = _minimal()
    diagram["nodes"][1]["props"]["fleet_kind"] = "pv"
    diagram["nodes"] += [
        _node("bus2", "busbar", fleet_kind="bess"),
        _node("s2", "station", mode="catalogue",
              model="GENERIC_BESS_TX_2750_LV069", fleet_kind="bess",
              bess_solution="sungrow-st6900ux-4h"),
        _node("aux2", "aux", p_kw=20.0, q_kvar=5.0),
    ]
    diagram["edges"] += [
        _edge("e_poc2", "poc", "bus2", length_m=0.0),
        _edge("e_t2", "bus2", "s2", length_m=300.0),
        _edge("e_aux2", "bus2", "aux2"),
    ]
    assert validate_graph(diagram, db) == []


def test_unpublished_switchgear_rating_falls_back_with_notice():
    # Huawei publishes no switchgear rated current, so every design drawing a
    # JUPITER station exercises the fallback. Silence must never mean "no
    # limit" — see ADR-0006.
    result = solve_diagram(_minimal(), db)

    assert result["issues"] == []
    notices = [w for w in result["results"]["warnings"]
               if w["code"] == "switchgear_rating_not_published"]
    assert len(notices) == 1
    assert "630 A" in notices[0]["message"]
    assert "Huawei" in notices[0]["message"]


def test_published_switchgear_rating_raises_no_notice():
    diagram = _minimal()
    diagram["nodes"][2]["props"].update({
        "model": "SUNGROW_MVS3200",
        "pv_inverter": "sungrow-sg350hx-20",
        "inverter_count": 10,
    })

    result = solve_diagram(diagram, db)

    assert result["issues"] == []
    assert not any(w["code"] == "switchgear_rating_not_published"
                   for w in result["results"]["warnings"])

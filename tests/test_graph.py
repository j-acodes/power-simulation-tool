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

import pytest

from fastapi.testclient import TestClient

from backend.main import app, db
from backend.solve import build_chain
from powertool import (
    arrange_plant,
    size_architecture,
    size_pv_inverters,
)
from powertool.graph import graph_to_inputs, map_results, validate_graph

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
                  "export_loss_pct_per_km": 0.10, "max_circuit_current_a": 400.0},
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
            _node("s1", "station", mode="catalogue", model="HUAWEI_JUPITER3000"),
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
    assert summary["correction_factor"] == pytest.approx(0.9784619708953294)
    assert summary["p_poc_refined_delivered_kw"] == pytest.approx(3000.0, rel=1e-6)


def test_unknown_keys_are_ignored():
    # Permissive parsing: the canvas carries cosmetic fields the engine never
    # reads, and the schema will grow. Unknown keys must not fail a drawing.
    diagram = _minimal()
    diagram["viewport"] = {"zoom": 1.4}
    diagram["nodes"][0]["selected"] = True
    diagram["nodes"][0]["props"]["colour"] = "red"
    diagram["edges"][0]["animated"] = True
    assert validate_graph(diagram, db) == []


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
    }
    assert validate_graph(diagram, db) == []
    inputs = graph_to_inputs(diagram, db)
    assert inputs.circuits[0][0].s_rated_kva == 3000.0

    # uk% below the resistive share implied by Pk: the loss model rejects it.
    diagram["nodes"][2]["props"]["uk_percent"] = 0.5
    assert "bad_props" in _codes(validate_graph(diagram, db))


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
        "mode": "catalogue", "model": "GENERIC_BESS_TX_2750_LV069", "fleet_kind": "bess",
        # GENERIC_BESS_TX_2750_LV069 is 0.69 kV; this solution's PCS is 1.0 kV.
        "bess_solution": "GENERIC_BESS_3MWH_LV100",
    }
    issues = validate_graph(diagram, db)
    assert "bess_lv_mismatch" in _codes(issues)
    assert any(i.node_id == "s1" for i in issues if i.code == "bess_lv_mismatch")


def test_bess_single_fleet_design_validates_and_solves_like_pv():
    # A discharging battery is modelled as a generator: with an identical
    # transformer, a BESS station must size to exactly the same numbers a PV
    # station would — sizing behaviour does not change in this ticket.
    identical_tx = {
        "mode": "custom", "name": "Identical station", "s_rated_kva": 3000.0,
        "uk_percent": 6.0, "pk_kw": 30.0, "p0_kw": 3.0, "i0_percent": 0.5,
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
        **identical_tx, "fleet_kind": "bess", "bess_solution": "GENERIC_BESS_5MWH_LV069",
    }
    assert validate_graph(bess, db) == []
    bess_result = client.post("/api/solve", json=bess).json()
    assert bess_result["issues"] == []

    assert bess_result["results"]["nodes"]["s1"] == pv_result["results"]["nodes"]["s1"]
    assert bess_result["results"]["summary"] == pv_result["results"]["summary"]


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
            _node("a1", "station", mode="catalogue", model="HUAWEI_JUPITER3000"),
            _node("b1", "station", mode="catalogue", model="HUAWEI_JUPITER9000"),
            _node("b2", "station", mode="catalogue", model="HUAWEI_JUPITER3000"),
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
    assert inputs.station_ids == [["a1"], ["b1", "b2"]]
    assert [[tx.s_rated_kva for tx in c] for c in inputs.circuits] == \
           [[3300], [9000, 3300]]
    assert inputs.segment_edge_ids == {
        (1, 1): "e_a1", (2, 1): "e_b1", (2, 2): "e_b2"}
    assert inputs.segment_lengths == {(1, 1): 0.9, (2, 1): 0.7, (2, 2): 0.25}
    assert len(inputs.segment_lengths) == inputs.n_stations  # complete map

    assert inputs.p_poc_kw == 20_000.0 and inputs.pf_target == 0.95
    assert inputs.v_mv_kv == 20.0 and inputs.v_hv_kv == 132.0
    assert inputs.hv_mode == "auto" and inputs.hv_transformer is None
    assert inputs.export_edge_id == "e_exp" and inputs.export_length_km == 1.5
    assert inputs.aux_ids == ["aux"]
    assert (inputs.aux_p_kw, inputs.aux_q_kvar) == (120.0, 40.0)
    assert inputs.fleet == [(db.transformer("HUAWEI_JUPITER3000"), 2),
                            (db.transformer("HUAWEI_JUPITER9000"), 1)]


def test_forced_section_reaches_the_engine_inputs():
    diagram = _hv_diagram()
    diagram["edges"][3]["sizing"] = {"mode": "forced", "cable": "AL_400_20kV"}
    assert validate_graph(diagram, db) == []
    inputs = graph_to_inputs(diagram, db)
    assert [c.name for c in inputs.segment_candidates[(2, 1)]] == ["AL_400_20kV"]
    assert list(inputs.segment_candidates) == [(2, 1)]  # only the pinned run


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


def test_mv_interconnection_sizes_the_drawn_export_run():
    # No MV/HV transformer: the POC -> busbar cable IS the export run, sized at
    # the MV voltage with its drawn length and the export %/km budget.
    diagram = _minimal()
    diagram["nodes"][0]["props"]["p_target_mw"] = 6.0
    diagram["edges"][0]["length_m"] = 2500.0
    diagram["nodes"].append(
        _node("s2", "station", mode="catalogue", model="HUAWEI_JUPITER3000"))
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


def test_over_current_warning_points_at_the_trunk():
    diagram = _hv_diagram()
    diagram["settings"]["rules"]["max_circuit_current_a"] = 50.0
    resp = client.post("/api/solve", json=diagram)
    assert resp.status_code == 200
    warnings = resp.json()["results"]["warnings"]
    over = [w for w in warnings if w["code"] == "circuit_over_current"]
    assert over and {w["edge_id"] for w in over} == {"e_a1", "e_b1"}


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
# The 45 MW example plant of the frozen Streamlit app (5x JUPITER9000 +
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
                           max_circuit_current_a=400.0,
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
    # Anchor the fixture: this is the arrangement the auto path produces today.
    assert layout.circuit_sizes == [2, 2, 2, 1, 1]
    assert [[p.transformer.s_rated_kva for p in c] for c in layout.circuit_plans] == \
           [[9000, 3300], [9000, 3300], [9000, 3300], [9000], [9000]]

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
    assert summary["fleet_loading"] == layout.fleet_loading
    assert summary["p_poc_delivered_kw"] == arch.p_poc_delivered_kw
    assert summary["q_poc_delivered_kvar"] == arch.q_poc_delivered_kvar
    assert summary["correction_factor"] == arch.correction_factor
    assert summary["s_inv_refined_kva"] == arch.s_inv_refined_kva
    assert summary["p_poc_refined_delivered_kw"] == arch.p_poc_refined_delivered_kw
    assert summary["total_cable_loss_kw"] == arch.total_cable_loss_kw
    assert summary["total_transformer_loss_kw"] == arch.total_transformer_loss_kw
    assert summary["worst_trunk_current_a"] == max(c.i_trunk_a for c in arch.circuits)
    assert summary["power_balance_ok"] and results["warnings"] == []
    assert summary["p_poc_refined_delivered_kw"] >= P_POC_KW

    # Every cable run: same section, same losses, keyed to the drawn edge.
    for circuit in arch.circuits:
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
    for circuit, ids in zip(arch.circuits, station_ids):
        for station, node_id in zip(circuit.stations, ids):
            drawn = results["nodes"][node_id]
            assert drawn["model"] == station.model
            assert drawn["p_lv_kw"] == station.p_lv_kw
            assert drawn["dp_tx_kw"] == station.dp_tx_kw
            assert drawn["s_mv_kva"] == station.s_mv_kva
            assert drawn["loading"] == station.loading

    # The auto-sized MV/HV transformer, on the drawn block.
    assert results["nodes"]["hv"]["s_rated_kva"] == arch.export.hv_transformer.s_rated_kva
    assert results["nodes"]["hv"]["dp_kw"] == arch.export.dp_tx_kw
    assert results["nodes"]["poc"]["p_target_kw"] == P_POC_KW
    assert math.isclose(results["nodes"]["bus"]["p_kw"],
                        sum(c.p_busbar_kw for c in arch.circuits), rel_tol=1e-12)


def test_golden_rearranging_the_drawing_changes_the_numbers():
    # Sanity on the golden test: it compares real numbers, not a tautology —
    # moving one station to another circuit must move the losses.
    _stage1, layout, arch = _auto_reference()
    diagram, _ids, _edges = _drawn_example(layout)

    # Hang circuit 4's lone 9 MVA station off the end of circuit 1: four
    # circuits now, one of them a three-station chain whose trunk carries much
    # more power over the same lengths.
    moved = {e["id"]: e for e in diagram["edges"]}
    moved["c4_seg1"]["source"] = "s1_2"
    resp = client.post("/api/solve", json=diagram)
    assert resp.status_code == 200
    body = resp.json()
    results = body["results"]
    assert body["issues"] == []
    assert results["summary"]["circuit_sizes"] == [3, 2, 2, 1]
    assert results["summary"]["total_cable_loss_kw"] > arch.total_cable_loss_kw
    # ... and the drawing is now over the 400 A feeder cap, flagged on its trunk.
    assert [w["edge_id"] for w in results["warnings"]
            if w["code"] == "circuit_over_current"] == ["c1_seg1"]


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

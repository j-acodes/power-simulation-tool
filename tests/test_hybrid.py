"""Hybrid-topology gates for ticket 05.

The ticket's headline criterion — "a hybrid design with zero BESS power
reproduces the PV-only result to within 1e-9" — is vacuous read literally: a
branch with a zero active target cannot be sized at all, so the design collapses
to single-fleet and the comparison passes without exercising anything. It is
split here into the two independent failures it was written to catch. This file
holds the TOPOLOGY half; the PHYSICS half is the golden-snapshot diff driven by
``.scratch/bess-module/golden_snapshot.py``, which the test suite cannot express
because it must compare against numbers captured before the refactor.

What the topology gate protects: a BESS busbar and its stations are *drawn* —
they validate, they parse, they reach the branch builder — and the design still
solves to exactly the PV-only numbers because the fleet's target is zero. A
degenerate branch that leaked so much as one aux kilowatt into the shared bus
would show up here, and nowhere else.
"""

import pytest

from fastapi.testclient import TestClient

from backend.main import app, db
from powertool.graph import validate_graph

from test_graph import _edge, _minimal, _node

client = TestClient(app)


def _hybrid_with_drawn_bess(p_target_bess_mw: float = 0.0) -> dict:
    """The minimal PV drawing plus a fully drawn, separately-busbarred BESS
    fleet whose point-of-connection target defaults to zero.

    Deliberately a *complete* BESS branch — its own busbar declaring its kind,
    its own station with a real BESS solution behind it, its own aux load — so
    that at a zero target the engine has every opportunity to let it contribute
    something and must still contribute nothing.
    """
    diagram = _minimal()
    diagram["nodes"][0]["props"]["p_target_bess_mw"] = p_target_bess_mw
    diagram["nodes"][1]["props"]["fleet_kind"] = "pv"
    diagram["nodes"] += [
        _node("bus_b", "busbar", fleet_kind="bess"),
        _node("s_b1", "station", mode="catalogue",
              model="GENERIC_BESS_TX_2750_LV069", fleet_kind="bess",
              bess_solution="GENERIC_BESS_5MWH_LV069"),
        _node("aux_b", "aux", p_kw=40.0, q_kvar=8.0),
    ]
    diagram["edges"] += [
        _edge("e_poc_b", "poc", "bus_b", length_m=0.0),
        _edge("e_tb1", "bus_b", "s_b1", length_m=600.0),
        _edge("e_aux_b", "bus_b", "aux_b"),
    ]
    return diagram


def test_drawn_bess_branch_at_zero_target_validates():
    # One busbar per fleet kind is legal; the old multiple_busbar rule must not
    # fire on a hybrid, and neither must any BESS-specific rule.
    assert validate_graph(_hybrid_with_drawn_bess(), db) == []


def test_drawn_bess_branch_at_zero_target_solves_exactly_like_pv_only():
    """The topology gate. Not `approx` on the summary alone — the WHOLE result
    payload must match, because a degenerate branch's most likely failure mode
    is contributing a small amount somewhere specific (an aux load at the shared
    bus, an extra station in the fleet total) rather than moving every number.
    """
    pv_only = client.post("/api/solve", json=_minimal()).json()
    hybrid = client.post("/api/solve", json=_hybrid_with_drawn_bess()).json()

    assert pv_only["issues"] == [] and pv_only["results"] is not None
    assert hybrid["issues"] == [] and hybrid["results"] is not None

    # The BESS nodes exist in the drawing, so the hybrid payload carries result
    # entries the PV-only one does not. Every node they SHARE must be identical,
    # and so must the plant summary.
    assert hybrid["results"]["summary"] == pv_only["results"]["summary"]
    for node_id, expected in pv_only["results"]["nodes"].items():
        assert hybrid["results"]["nodes"][node_id] == expected, node_id


def test_a_real_hybrid_sizes_both_fleets_independently():
    """The other side of the gate: with a positive BESS target the branch must
    actually appear, and the PV fleet's own figures must move — a hybrid that
    silently ignored the second fleet would pass the zero-target test above.
    """
    hybrid = client.post("/api/solve",
                         json=_hybrid_with_drawn_bess(p_target_bess_mw=2.0)).json()
    assert hybrid["issues"] == [], hybrid["issues"]
    summary = hybrid["results"]["summary"]

    # The shared HV/export step now carries both fleets, so the PV branch's own
    # refined requirement cannot equal what it was alone.
    pv_only = client.post("/api/solve", json=_minimal()).json()
    assert summary != pv_only["results"]["summary"]
    # "kind" is the canvas node type and stays "station" for every station;
    # the fleet is a separate axis with its own key.
    assert hybrid["results"]["nodes"]["s_b1"]["kind"] == "station"
    assert hybrid["results"]["nodes"]["s_b1"]["fleet_kind"] == "bess"
    assert hybrid["results"]["nodes"]["s1"]["fleet_kind"] == "pv"


def test_pdf_report_refuses_a_hybrid_rather_than_reporting_one_fleet():
    """The PDF is still single-fleet (ticket 08 owns hybrid reporting). It must
    REFUSE rather than build a report off the first branch: a document titled
    with the whole plant while describing half of it is the artefact that leaves
    the building, and nothing on the page would admit the other fleet exists.
    """
    response = client.post("/api/report", params={"name": "Hybrid plant"},
                           json=_hybrid_with_drawn_bess(p_target_bess_mw=2.0))
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "single-fleet" in detail and "pv, bess" in detail

    # The same endpoint must still produce a PDF for a single-fleet design —
    # the refusal is scoped to the case the report cannot represent.
    ok = client.post("/api/report", params={"name": "PV plant"}, json=_minimal())
    assert ok.status_code == 200
    assert ok.content[:4] == b"%PDF"


def test_max_loading_is_per_fleet_kind_and_falls_back_to_the_plant_rule():
    """A BESS fleet is routinely held to a different loading limit than a PV
    one, but a design that only ever set the single plant-wide value must keep
    meaning what it meant.
    """
    from powertool.graph import graph_to_inputs

    # Fallback: only the plant-wide rule is set, so both fleets read it.
    shared = _hybrid_with_drawn_bess(p_target_bess_mw=2.0)
    shared["settings"]["rules"]["max_loading"] = 0.85
    by_kind = {b.kind: b.max_loading for b in graph_to_inputs(shared, db).branches}
    assert by_kind == {"pv": 0.85, "bess": 0.85}

    # Per-kind overrides win, each only over its own fleet.
    split = _hybrid_with_drawn_bess(p_target_bess_mw=2.0)
    split["settings"]["rules"]["max_loading"] = 0.85
    split["settings"]["rules"]["max_loading_bess"] = 0.70
    by_kind = {b.kind: b.max_loading for b in graph_to_inputs(split, db).branches}
    assert by_kind == {"pv": 0.85, "bess": 0.70}


def test_a_legacy_bess_plant_can_gain_a_pv_busbar():
    """Upgrading a single-fleet BESS plant to a hybrid must be legal.

    The busbar in every pre-hybrid design declares no `fleet_kind`. Reading the
    bare "pv" default when deciding which fleet SLOT a busbar occupies would put
    a BESS plant's busbar in the PV slot, so adding a PV busbar to it would come
    back as a duplicate — while the very same busbar is simultaneously solved as
    a BESS branch. The slot a busbar occupies and the fleet it is sized as have
    to be the same answer.
    """
    diagram = _minimal()
    diagram["settings"]["tiers"]["lv_kv"] = 0.69
    diagram["nodes"][2]["props"] = {
        "mode": "catalogue", "model": "GENERIC_BESS_TX_2750_LV069",
        "fleet_kind": "bess", "bess_solution": "GENERIC_BESS_5MWH_LV069",
    }
    # The busbar deliberately keeps no fleet_kind — that is what a saved design
    # looks like. Add a declared PV busbar with a station of its own.
    diagram["nodes"] += [
        _node("bus_pv", "busbar", fleet_kind="pv"),
        _node("s_pv", "station", mode="catalogue", model="HUAWEI_JUPITER3000"),
    ]
    diagram["edges"] += [
        _edge("e_poc_pv", "poc", "bus_pv", length_m=0.0),
        _edge("e_tpv", "bus_pv", "s_pv", length_m=700.0),
    ]
    assert [i.code for i in validate_graph(diagram, db)] == []


def test_two_undeclared_busbars_are_still_a_duplicate():
    """The relaxation must not become "anything goes": two busbars that both
    read as the same fleet are still a duplicate, whether declared or derived.
    """
    diagram = _minimal()
    diagram["nodes"] += [
        _node("bus2", "busbar"),
        _node("s2", "station", mode="catalogue", model="HUAWEI_JUPITER3000"),
    ]
    diagram["edges"] += [
        _edge("e_poc2", "poc", "bus2", length_m=0.0),
        _edge("e_t2", "bus2", "s2", length_m=700.0),
    ]
    issues = validate_graph(diagram, db)
    assert "duplicate_busbar" in {i.code for i in issues}


# --- BESS sizing and compliance (ticket 07) ---------------------------------

def _bess_only(duration=None, model="GENERIC_BESS_TX_2750_LV069",
               solution="GENERIC_BESS_5MWH_LV069", p_target_mw=3.0):
    """A single-fleet BESS plant, optionally with a discharge duration set."""
    d = _minimal()
    d["settings"]["tiers"]["lv_kv"] = 0.69
    d["nodes"][0]["props"]["p_target_mw"] = p_target_mw
    d["nodes"][1]["props"]["fleet_kind"] = "bess"
    d["nodes"][2]["props"] = {"mode": "catalogue", "model": model,
                              "fleet_kind": "bess", "bess_solution": solution}
    if duration is not None:
        d["settings"]["rules"]["discharge_hours"] = duration
    return d


def test_container_count_and_delivered_energy_come_from_the_table():
    from powertool.graph import graph_to_inputs
    # GENERIC_BESS_5MWH_LV069: 4 containers at 2 h, 8 at 4 h, 5000 kWh each.
    for hours, per_station in ((2.0, 4), (4.0, 8)):
        branch = graph_to_inputs(_bess_only(duration=hours), db).branches[0]
        assert branch.containers == per_station          # one station drawn
        assert branch.e_delivered_kwh == per_station * 5000.0


def test_an_unsupported_duration_is_rejected_server_side():
    # The UI offers a select, so this is only reachable by hand-editing the
    # payload — which is exactly why it is checked here rather than trusted.
    issues = validate_graph(_bess_only(duration=3.0), db)
    assert "unsupported_duration" in {i.code for i in issues}


def test_a_supported_duration_validates():
    assert validate_graph(_bess_only(duration=4.0), db) == []


def test_a_bess_design_without_a_duration_still_solves():
    # Every design saved before this ticket has no discharge_hours. It must keep
    # working; the energy gate simply has nothing to judge it against.
    from powertool.graph import graph_to_inputs
    assert validate_graph(_bess_only(), db) == []
    branch = graph_to_inputs(_bess_only(), db).branches[0]
    assert branch.containers is None and branch.e_delivered_kwh is None


def test_the_energy_gate_is_independent_of_the_loading_gate():
    """Both gates are hard, and an engineer has to see WHICH one failed.

    One drawn station of GENERIC_BESS_5MWH_LV069 gives 8 containers at 4 h
    (read from the table, not derived), so 40 MWh delivered whatever the target.
    Raising the target raises the energy owed without touching what is
    installed, which is how the two gates are pulled apart here.
    """
    ok = client.post("/api/solve", json=_bess_only(duration=4.0, p_target_mw=3.0)).json()
    assert ok["issues"] == []
    fleet = ok["results"]["summary"]["branches"][0]
    assert fleet["containers"] == 8
    assert fleet["e_delivered_kwh"] == 40_000.0
    assert fleet["e_required_kwh"] == 12_000.0   # 3 MW for 4 h
    assert fleet["energy_ok"] is True

    # 12 MW for 4 h owes 48 MWh; the same single station still delivers 40 MWh.
    short = client.post("/api/solve", json=_bess_only(duration=4.0, p_target_mw=12.0)).json()
    fleet = short["results"]["summary"]["branches"][0]
    assert fleet["e_delivered_kwh"] == 40_000.0
    assert fleet["e_required_kwh"] == 48_000.0
    assert fleet["energy_ok"] is False
    # ...and the loading gate is reported separately, against this fleet's own
    # maximum, so the engineer can tell the two failures apart.
    assert fleet["loading_ok"] is False
    assert fleet["max_loading"] == 1.0


def test_bess_aux_is_reported_but_never_sizes_the_pcs():
    """A battery station's PCS is sized for export duty alone.

    Keeping the solution's auxiliary draw out of the Stage-1 chain is NOT enough
    on its own, and that is the trap this test exists for. The refinement drives
    each branch's delivered power up to its target, so an auxiliary load
    subtracted at the busbar gets compensated straight back into the refined
    conversion figure — the PCS is upsized to carry it by the back door, while
    the nameplate figure stays innocently clean. Asserting only `s_inv_kva`
    proves nothing: it CANNOT move, because the aux is never passed to
    size_generation_pq. The refined figure is the one that sizes real equipment,
    so it is the one asserted here.
    """
    import dataclasses
    from powertool.database import ComponentDatabase
    from backend.solve import solve_diagram

    design = _bess_only(duration=4.0)
    design["nodes"] = [n for n in design["nodes"] if n["kind"] != "aux"]
    design["edges"] = [e for e in design["edges"] if e["id"] != "e_aux"]

    # The same design against a catalogue whose solution draws no auxiliary
    # power at all. Every sizing figure must be identical.
    zero_aux = dataclasses.replace(db.bess_solutions["GENERIC_BESS_5MWH_LV069"],
                                   aux_p_kw=0.0, aux_q_kvar=0.0)
    db_zero = ComponentDatabase(db.cables, db.transformers,
                                {**db.bess_solutions,
                                 "GENERIC_BESS_5MWH_LV069": zero_aux},
                                db.bess_transformers)

    with_aux = solve_diagram(design, db)
    without = solve_diagram(design, db_zero)
    assert with_aux["issues"] == [] and without["issues"] == []
    a = with_aux["results"]["summary"]["branches"][0]
    b = without["results"]["summary"]["branches"][0]

    for key in ("s_inv_kva", "s_inv_refined_kva", "p_inv_refined_kw",
                "correction_factor", "p_poc_delivered_kw",
                "p_poc_refined_delivered_kw"):
        assert a[key] == pytest.approx(b[key]), key

    # Reported all the same — the site still has to supply it.
    assert a["bess_aux_p_kw"] == 40.0     # one station, worst case from the sheet
    assert a["bess_aux_q_kvar"] == 10.0
    assert b["bess_aux_p_kw"] == 0.0


def test_bess_aux_is_summed_across_the_fleet():
    from powertool.graph import graph_to_inputs
    design = _bess_only(duration=4.0)
    branch = graph_to_inputs(design, db).branches[0]
    assert branch.bess_aux_p_kw == 40.0
    assert branch.bess_aux_q_kvar == 10.0
    # The drawn aux node is a separate figure and stays separate.
    assert branch.aux_p_kw == 50.0


def test_container_count_is_reported_on_each_station():
    solved = client.post("/api/solve", json=_bess_only(duration=2.0)).json()
    assert solved["issues"] == []
    assert solved["results"]["nodes"]["s1"]["containers"] == 4
    # A PV station has no container count at all, rather than a zero that would
    # read as "none needed".
    pv = client.post("/api/solve", json=_minimal()).json()
    assert "containers" not in pv["results"]["nodes"]["s1"]

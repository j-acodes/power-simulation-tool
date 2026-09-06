"""Hybrid-topology gates for ticket 05.

The ticket's headline criterion — "a hybrid design with zero BESS power
reproduces the PV-only result to within 1e-9" — is vacuous read literally: a
branch with a zero active target cannot be sized at all, so the design collapses
to single-fleet and the comparison passes without exercising anything. It is
split here into the two independent failures it was written to catch. This file
holds the TOPOLOGY half; the PHYSICS half is the golden snapshot, which was a
manual script compared against numbers captured before a refactor and is now
``tests/test_golden_snapshot.py``, compared against a committed baseline.

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
              bess_solution="sungrow-st6900ux-4h"),
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


def test_split_reactive_always_divides_pro_rata_by_active_power():
    """Ticket 01: the reactive split has no share argument any more — pro-rata
    by active power is the only behaviour, not just the default. A lone branch
    still takes the whole combined duty regardless (see the function's own
    docstring), which is what keeps a zero-BESS hybrid identical to PV-only.
    """
    from types import SimpleNamespace

    from backend.solve import _split_reactive

    pv = SimpleNamespace(kind="pv", p_poc_target_kw=3000.0)
    bess = SimpleNamespace(kind="bess", p_poc_target_kw=1000.0)
    q_pv, q_bess = _split_reactive([pv, bess], 400.0)
    assert q_pv == pytest.approx(300.0)
    assert q_bess == pytest.approx(100.0)

    assert _split_reactive([pv], 400.0) == [400.0]


def test_the_pdf_endpoint_reports_a_hybrid_rather_than_refusing_it():
    """Ticket 07 made this a deliberate 400: the report was single-fleet, so it
    could only have described the first fleet with the second silently missing,
    and a report that is quietly wrong is worse than no report. Ticket 08 taught
    the report about fleets, so the refusal is gone — asserted here, at the
    endpoint, because that is where the refusal lived.
    """
    response = client.post("/api/report", params={"name": "Hybrid plant"},
                           json=_hybrid_with_drawn_bess(p_target_bess_mw=2.0))
    assert response.status_code == 200
    assert response.content[:4] == b"%PDF"

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
        "fleet_kind": "bess", "bess_solution": "sungrow-st6900ux-4h",
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
               solution="sungrow-st6900ux-4h", p_target_mw=3.0):
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


def test_container_count_and_delivered_energy_come_from_the_declared_duration():
    from powertool.graph import graph_to_inputs
    # sungrow-st6900ux-4h: 1 container at its declared 4 h duration, 6904 kWh.
    branch = graph_to_inputs(_bess_only(duration=4.0), db).branches[0]
    assert branch.containers == 1          # one station drawn
    assert branch.e_delivered_kwh == 6904.0


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

    One drawn station of sungrow-st6900ux-4h delivers exactly its declared
    6904 kWh at its 4 h duration (read from the datasheet, not derived),
    whatever the target. Raising the target raises the energy owed without
    touching what is installed, which is how the two gates are pulled apart
    here.
    """
    ok = client.post("/api/solve", json=_bess_only(duration=4.0, p_target_mw=1.0)).json()
    assert ok["issues"] == []
    fleet = ok["results"]["summary"]["branches"][0]
    assert fleet["containers"] == 1
    assert fleet["e_delivered_kwh"] == 6904.0
    assert fleet["e_required_kwh"] == 4_000.0   # 1 MW for 4 h
    assert fleet["energy_ok"] is True

    # 12 MW for 4 h owes 48 MWh; the same single station still delivers 6904 kWh.
    short = client.post("/api/solve", json=_bess_only(duration=4.0, p_target_mw=12.0)).json()
    fleet = short["results"]["summary"]["branches"][0]
    assert fleet["e_delivered_kwh"] == 6904.0
    assert fleet["e_required_kwh"] == 48_000.0
    assert fleet["energy_ok"] is False
    # ...and the loading gate is reported separately, against this fleet's own
    # maximum, so the engineer can tell the two failures apart.
    assert fleet["loading_ok"] is False
    assert fleet["max_loading"] == 1.0


def _db_with_bess_aux(p_kw: float, q_kvar: float):
    """The catalogue, with the Sungrow solution given a non-zero auxiliary draw.

    sungrow-st6900ux-4h publishes no auxiliary figure, so every test that needs
    a non-zero one has to invent it. Inventing it in one place keeps the tests
    about auxiliary load rather than about assembling a catalogue.
    """
    import dataclasses
    from powertool.database import ComponentDatabase

    with_aux = dataclasses.replace(db.bess_solutions["sungrow-st6900ux-4h"],
                                   aux_p_kw=p_kw, aux_q_kvar=q_kvar)
    return ComponentDatabase(db.cables, db.transformers,
                             {**db.bess_solutions, "sungrow-st6900ux-4h": with_aux},
                             db.bess_transformers, db.bess_pairings)


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
    from backend.solve import solve_diagram

    design = _bess_only(duration=4.0)
    design["nodes"] = [n for n in design["nodes"] if n["kind"] != "aux"]
    design["edges"] = [e for e in design["edges"] if e["id"] != "e_aux"]

    # sungrow-st6900ux-4h publishes no auxiliary figure (zero, per the
    # datasheet). Compare it against a hypothetical catalogue entry that draws
    # a non-zero worst-case auxiliary load — every sizing figure must be
    # identical regardless.
    db_with_aux = _db_with_bess_aux(40.0, 10.0)

    with_aux = solve_diagram(design, db_with_aux)
    without = solve_diagram(design, db)
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

    # sungrow-st6900ux-4h publishes no auxiliary figure; a non-zero one is what
    # proves the figure reaches the branch total.
    db_with_aux = _db_with_bess_aux(40.0, 10.0)

    design = _bess_only(duration=4.0)
    branch = graph_to_inputs(design, db_with_aux).branches[0]
    assert branch.bess_aux_p_kw == 40.0
    assert branch.bess_aux_q_kvar == 10.0
    # The drawn aux node is a separate figure and stays separate.
    assert branch.aux_p_kw == 50.0


def test_unpublished_aux_raises_an_informational_notice_but_does_not_block():
    """sungrow-st6900ux-4h publishes no auxiliary figure (ticket 07 of
    component-datasheets). The design must still solve, still carry zero
    validation issues, and still pass compliance — the notice is informational,
    riding on the results as a warning, not a validation issue.
    """
    resp = client.post("/api/solve", json=_bess_only(duration=4.0))
    body = resp.json()
    assert body["issues"] == []                # not blocked
    assert body["results"] is not None          # still solves
    warnings = body["results"]["warnings"]
    notices = [w for w in warnings if w["code"] == "bess_aux_not_published"]
    assert len(notices) == 1
    assert "PowerTitan 3.0 — ST6900UX-4H" in notices[0]["message"]
    assert notices[0]["node_id"] == "bus"


def test_a_published_aux_figure_raises_no_notice():
    db_with_aux = _db_with_bess_aux(40.0, 10.0)
    from backend.solve import solve_diagram

    result = solve_diagram(_bess_only(duration=4.0), db_with_aux)
    assert result["issues"] == []
    warnings = result["results"]["warnings"]
    assert [w for w in warnings if w["code"] == "bess_aux_not_published"] == []


def test_an_existing_error_severity_issue_still_blocks():
    # An unknown solution is still an ERROR: it still refuses to solve, unlike
    # the informational notice above.
    diagram = _bess_only(duration=4.0, solution="does-not-exist")
    resp = client.post("/api/solve", json=diagram)
    body = resp.json()
    assert body["results"] is None
    assert "unknown_bess_solution" in {i["code"] for i in body["issues"]}


def test_container_count_is_reported_on_each_station():
    solved = client.post("/api/solve", json=_bess_only(duration=4.0)).json()
    assert solved["issues"] == []
    assert solved["results"]["nodes"]["s1"]["containers"] == 1
    # A PV station has no container count at all, rather than a zero that would
    # read as "none needed".
    pv = client.post("/api/solve", json=_minimal()).json()
    assert "containers" not in pv["results"]["nodes"]["s1"]

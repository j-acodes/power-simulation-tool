"""Numerical snapshot of the engine, keyed by design.

Every other test in this suite asserts a number someone chose to assert. This
one asserts ALL of them: it drives ``solve_diagram`` over designs picked to
exercise different code paths and captures every value they produce, so a
refactor that quietly moves a figure nobody thought to pin still fails.

The baseline lives beside this file as ``golden_baseline.json`` and
``test_golden_snapshot.py`` compares against it. **Regenerate deliberately, and
read the diff:**

    .venv/bin/python -m tests.golden_snapshot    # rewrites golden_baseline.json
    git diff tests/golden_baseline.json          # this is the part that matters

COVERAGE. Cases 1-8 are PV-only. For a long time they were the whole file,
which made the snapshot silently blind to battery work: the component-datasheet
tickets rewrote ``BessSolution``, deleted its duration table and moved the
container count onto the station transformer, and this reported an empty diff
throughout, because not one fixture drew a BESS station. Cases 9-14 close that.
They exercise the container count (from the pairing and from a manual
override), the declared discharge duration, delivered energy, the per-fleet
auxiliary draw, and a hybrid carrying both fleets at once.

Anything added here should exercise a path the others do not. A fixture that
merely varies a number the others already cover costs a baseline entry and
buys nothing.
"""
import json
import sys
from pathlib import Path

from backend.seed import seed_diagram
from backend.solve import solve_diagram
from powertool.database import ComponentDatabase

# The fixture designs live in the test modules beside this one. pytest puts this
# directory on the path itself; running this file directly to regenerate the
# baseline does not, so do it here rather than only working under pytest.
sys.path.insert(0, str(Path(__file__).parent))

from test_graph import _minimal  # noqa: E402
from test_hybrid import _bess_only, _hybrid_with_drawn_bess  # noqa: E402

BASELINE = Path(__file__).parent / "golden_baseline.json"


def build_snapshot(db: ComponentDatabase) -> dict:
    """Every number the engine produces for the fixture designs, keyed by case."""
    out: dict = {}

    # 1-3: the minimal MV-interconnected drawing, varying the POC duty.
    for label, p_mw, pf in (("min_3mw_pf095", 3.0, 0.95),
                            ("min_3mw_pf1", 3.0, 1.0),
                            ("min_12mw_pf090", 12.0, 0.90)):
        d = _minimal()
        d["nodes"][0]["props"]["p_target_mw"] = p_mw
        d["nodes"][0]["props"]["pf"] = pf
        out[label] = solve_diagram(d, db)

    # 4: no aux load at all (drops a term from the busbar balance).
    d = _minimal()
    d["nodes"] = [n for n in d["nodes"] if n["kind"] != "aux"]
    d["edges"] = [e for e in d["edges"] if e["id"] != "e_aux"]
    out["min_no_aux"] = solve_diagram(d, db)

    # 5-8: seeded plants — multi-circuit arrangements, HV and MV interconnection,
    # which is where the export step and the refinement loop actually do work.
    seeds = {
        "seed_45mw_hv": dict(p_poc_mw=45.0, interconnection="HV", v_hv_kv=132.0, export_m=1500.0),
        "seed_45mw_mv": dict(p_poc_mw=45.0, interconnection="MV", export_m=0.0),
        "seed_10mw_hv": dict(p_poc_mw=10.0, interconnection="HV", v_hv_kv=132.0, export_m=500.0),
        "seed_120mw_hv": dict(p_poc_mw=120.0, interconnection="HV", v_hv_kv=220.0, export_m=4000.0),
    }
    for label, extra in seeds.items():
        req = dict(pf_target=0.95, v_mv_kv=20.0, station_model="SUNGROW_MVS4480",
                   max_loading=0.9, trunk_m=400.0, spacing_m=120.0,
                   max_circuit_current_a=400.0, aux_p_kw=250.0, aux_q_kvar=60.0, **extra)
        diagram = seed_diagram(req, db)
        out[label] = {"diagram_nodes": len(diagram["nodes"]),
                      "solved": solve_diagram(diagram, db)}

    # 9-11: BESS-only, varying the duty and the station transformer. The two
    # transformers differ in what they are PAIRED to serve — 2750 kVA carries one
    # container, 4000 kVA carries two — so these pin the pairing lookup and the
    # delivered-energy sum, not just the sizing cascade.
    out["bess_3mw_4h_tx2750"] = solve_diagram(_bess_only(duration=4.0), db)
    out["bess_3mw_4h_tx4000"] = solve_diagram(
        _bess_only(duration=4.0, model="GENERIC_BESS_TX_4000_LV069"), db)
    out["bess_12mw_4h_tx4000"] = solve_diagram(
        _bess_only(duration=4.0, model="GENERIC_BESS_TX_4000_LV069", p_target_mw=12.0), db)

    # 12: no discharge duration set. The energy gate does not apply and delivered
    # energy stays absent — a regression that started computing one anyway would
    # show up here and in no other fixture.
    out["bess_3mw_no_duration"] = solve_diagram(_bess_only(), db)

    # 13: a manual container override on a partially populated station. This is the
    # one place a container count is a judgement rather than a supplier's figure,
    # so it needs pinning independently of the pairing default it replaces.
    d = _bess_only(duration=4.0, model="GENERIC_BESS_TX_4000_LV069")
    d["nodes"][2]["props"]["containers_override"] = 1
    out["bess_3mw_4h_override_1"] = solve_diagram(d, db)

    # 14: hybrid, both fleets drawn and both carrying real duty. The PV and BESS
    # cascades are independent by design; this is what catches one leaking into
    # the other.
    hybrid = _hybrid_with_drawn_bess(p_target_bess_mw=3.0)
    hybrid["settings"]["rules"]["discharge_hours"] = 4.0
    out["hybrid_pv_and_bess_3mw_4h"] = solve_diagram(hybrid, db)

    return out


def _serialise(snapshot: dict) -> str:
    return json.dumps(snapshot, sort_keys=True, indent=2, default=str) + "\n"


if __name__ == "__main__":
    BASELINE.write_text(_serialise(build_snapshot(ComponentDatabase.load())))
    print(f"wrote {BASELINE}")

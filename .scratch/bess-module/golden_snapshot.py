"""Independent numerical snapshot of the engine, keyed by design.

USAGE — capture before a refactor, compare after:

    git worktree add --detach /tmp/pristine HEAD
    cd /tmp/pristine && <repo>/.venv/bin/python <this file> > /tmp/before.json
    cd <repo> && .venv/bin/python <this file> > /tmp/after.json
    diff /tmp/before.json /tmp/after.json     # must be empty
    git worktree remove /tmp/pristine --force

Written for ticket 04, whose acceptance criterion was the existing suite
passing UNEDITED — which is precisely why the suite could not also be the
evidence that no number moved. Reusable for ticket 05, which needs a golden
hybrid-with-zero-BESS comparison against the PV-only result.

Deliberately avoids the test suite: ticket 04's acceptance gate IS the suite
passing unedited, so the suite cannot also serve as the evidence that no number
moved. This drives solve_diagram over designs chosen to exercise different code
paths and dumps every number they produce.
"""
import json, sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests")
from backend.solve import solve_diagram          # noqa: E402
from backend.seed import seed_diagram            # noqa: E402
from powertool.database import ComponentDatabase  # noqa: E402
from test_graph import _minimal                   # noqa: E402

db = ComponentDatabase.load()
out = {}

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
    "seed_45mw_hv":  dict(p_poc_mw=45.0, interconnection="HV", v_hv_kv=132.0, export_m=1500.0),
    "seed_45mw_mv":  dict(p_poc_mw=45.0, interconnection="MV", export_m=0.0),
    "seed_10mw_hv":  dict(p_poc_mw=10.0, interconnection="HV", v_hv_kv=132.0, export_m=500.0),
    "seed_120mw_hv": dict(p_poc_mw=120.0, interconnection="HV", v_hv_kv=220.0, export_m=4000.0),
}
for label, extra in seeds.items():
    req = dict(pf_target=0.95, v_mv_kv=20.0, station_model="SUNGROW_MVS4480",
               max_loading=0.9, trunk_m=400.0, spacing_m=120.0,
               max_circuit_current_a=400.0, aux_p_kw=250.0, aux_q_kvar=60.0, **extra)
    diagram = seed_diagram(req, db)
    out[label] = {"diagram_nodes": len(diagram["nodes"]), "solved": solve_diagram(diagram, db)}

print(json.dumps(out, sort_keys=True, default=str))

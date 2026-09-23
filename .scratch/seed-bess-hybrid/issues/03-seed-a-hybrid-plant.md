# 03: Seed a hybrid plant

**What to build:** On a hybrid design the seed wizard shows a PV section and a BESS section. Each
fleet has its own point-of-connection power, maximum loading, trunk length and spacing; export
length, interconnection, voltages, power-factor target, auxiliary load and feeders per busbar are
shared. The seed sizes each fleet as its own cascade (PV as today, BESS as ticket 02) behind the
one shared HV transformer or point of connection, iterating a fleet's count if the real
multi-branch solve shows it undersized. The substation auxiliary load goes on the first PV busbar.
Layout: point of connection and HV transformer centred, PV busbars and circuits left, BESS right.

**Key interfaces:**
- `seed_diagram(params, db)` dispatches on `technology` to `_seed_pv` / `_seed_bess`; `"hybrid"`
  currently raises `ValueError`. Both fleet paths size a count (PV on inverter capacity; BESS on
  installed PCS, station rating at ambient × `max_loading_bess`, and energy), call
  `arrange_plant(...)`, then render with `_layout_to_diagram` / `_layout_to_diagram_bess`. Reuse
  the sizing parts of both; `_seed_pv` and `_seed_bess` output must stay unchanged for PV-only and
  BESS-only requests.
- `SeedRequest` already carries both blocks and requires each when the technology permits it
  (hybrid requires both). Per-fleet fields: PV `p_poc_mw`, `max_loading`, `trunk_m`, `spacing_m`;
  BESS `p_poc_bess_mw`, `max_loading_bess`, `trunk_bess_m`, `spacing_bess_m`.
- Hybrid POC semantics (engine, `graph_to_inputs`): `p_target_mw` is the PV figure and
  `p_target_bess_mw` the BESS figure when both fleet kinds are drawn. Rules: `max_loading_pv`,
  `max_loading_bess`, `discharge_hours`. Drawn hybrid shape: `_hybrid_with_drawn_bess()` in
  `tests/test_hybrid.py`.
- "Iterate if the real solve shows a fleet undersized": after building the diagram, run the real
  diagram solve (as the seed tests do) and, while a fleet's loading/PCS/inverter check fails,
  add one station to that fleet and rebuild; cap the iterations and raise if still failing.
- Tests must use loading limits below 1.0 (e.g. 0.8 BESS / the PV default); ticket 02's tests
  hid an overload by using 1.0.
- Frontend: `SeedWizard.tsx` renders the PV block or the BESS block depending on
  `designMeta.technology`; hybrid renders both, with shared fields once. `EditorView.tsx` already
  shows the seed button whenever PV or BESS is permitted.

**Blocked by:** 02: Seed a BESS plant.

**Status:** ready-for-agent

- [ ] Seeded hybrid carries both fleet power figures on the point of connection and per-kind maximum-loading rules
- [ ] Seeded hybrid validates and solves with both fleets within their loading limits and energy met
- [ ] Both HV and MV interconnection variants seed and solve
- [ ] Auxiliary load hangs off the first PV busbar
- [ ] PV nodes sit left of BESS nodes; point of connection is centred over both
- [ ] Wizard on a hybrid design shows both sections with per-fleet lengths and loading
- [ ] PV-only and BESS-only seeding unchanged
- [ ] Focused seed tests, wizard test and type checks pass

## Comments

- 2026-09-23 (ticket 02 implementer): `frontend/src/technology.ts` `convertDiagramTechnology`
  zeroes/reads `p_target_bess_mw` when cloning a BESS-only design to/from hybrid. A BESS-only
  design carries its target on `p_target_mw`, so the BESS figure may not carry over on a clone.
  Check while touching hybrid POC fields.

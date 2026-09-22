# 01: Retire the flat cap; station switchgear groups circuits

**What to build:** circuit grouping is decided by each station's switchgear rated current, not
by the flat 400 A `max_circuit_current_a`. Stage-1 planning keeps its biggest-station-nearest
ordering and packs stations so every station's through current stays within its own switchgear
rated current (630 A fallback applies as shipped). A drawn diagram keeps its order and is only
checked. The flat cap is deleted everywhere: rule defaults, rule reader, `PlantLayout`, solve
inputs, API schemas, seed parameters, the settings control and the PDF report. A saved design
still carrying the key in `settings.rules` ignores it. See ADR-0006, ADR-0007 and the spec.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Stage-1 grouping admits a circuit only when every position's accumulated through current is within that position's station switchgear rated current; the `test_assign_*` family asserts that, not scalar-cap semantics
- [x] `max_circuit_current_a` no longer exists in engine, backend, API, frontend, seed or PDF; a diagram carrying it in `settings.rules` solves identically to one without it
- [x] Before `tests/golden_baseline.json` is regenerated, one design's circuit count and trunk through current are computed by hand and pinned as an explicit test that passes
- [x] Golden baseline regenerated after the anchor passes; the commit message explains why the numbers moved
- [x] `.venv/bin/python -m pytest -q`, frontend Vitest, `npm run build` and `npm run lint` pass
- [x] Report states that a DB reset is required at ship time (settings key removed); do not run `scripts/reset_db.py`

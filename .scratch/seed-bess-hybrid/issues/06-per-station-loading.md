# 06: Seed keeps every BESS station within loading; overload messages name the worst station

**What to build:** Two defects the owner found on 2026-09-23 by seeding a BESS example.

1. **Seed.** Since ticket 01, BESS duty is shared by installed PCS (ADR-0008), so when the last
   station holds fewer containers, every full station carries more than the fleet average.
   `loading_ok` is per station (any station above `max_loading` fails), but the ticket 02 fix
   (06433fa) bounded the station count by the fleet *average*. Repro (wizard defaults): BESS,
   pf 0.95, HV 132 kV, MV 20 kV, export 0 m, 4 h, `sungrow-st6900ux-4h`, `SUNGROW_MVS7400_LS`,
   `max_loading_bess` 0.8, trunk 800 m, spacing 350 m, aux 120 kW / 40 kvar. With
   `p_poc_bess_mw` = 25, 30, 35, 45 or 50, the last station is partial and `loading_ok` is False
   while `fleet_loading` ≈ 0.78. 20, 40 and 60 MW pass.
2. **Message.** Both the engine's `fleet_overloaded` warning and the frontend compliance reason
   quote the fleet *average*, so the owner saw "overloaded — 78 % … against an 80 % maximum". The
   BESS warning's comment "BESS allocation remains proportional to transformer rating" is stale.

**Decision (coordinator, 2026-09-23):** fix the seed with containers, not stations. A full
station's duty is `S_fleet × maximum / C_total`, so the total container count must also satisfy
`C_total ≥ ceil(S_fleet × maximum / station_limit)`, with `station_limit =
station.rating_at(ambient) × max_loading_bess`, and `S_fleet` the Stage-1 `s_inv_kva` for the
fleet. Required containers = max(energy-driven, loading-driven); station count and
`_bess_containers` fill follow from that as today. Adding stations alone does not help while the
container total is fixed.

**Key interfaces:**
- `_size_bess_fleet` in `backend/seed.py` (`required`, `_bess_containers`, `station_limit`).
  Hybrid reuses it; its real-solve iteration stays.
- Per-station loading lives in the circuit plans (`plan.loading`); `loading_ok` is computed in
  `powertool/architecture.py` (the `loading_ok = all(plan.loading <= max_loading ...)` sites).
  Add `max_station_loading` (the largest `plan.loading` in the fleet) to the per-branch summary
  in `powertool/graph.py` (next to `fleet_loading` / `loading_ok`), and to the frontend
  `BranchSummary` type.
- Engine warning (`fleet_overloaded`, both PV and BESS wording) and `fleetReasons` in
  `frontend/src/compliance.ts`: say the worst station's loading against the limit, and keep the
  fleet average as context, e.g. "The BESS fleet is overloaded — its most loaded station is at
  83 % against an 80 % maximum (fleet average 78 %)." Drop the stale BESS comment.
- Golden baseline: the new summary key appears in every case; BESS seeded numbers don't exist
  in the baseline. Regenerate and confirm the only change is the added key (and warning text
  where an overload is pinned).

**Blocked by:** None.

**Status:** done

- [x] Parametrised seed test over `p_poc_bess_mw` ∈ {20, 25, 30, 35, 40, 45, 50, 60} with the
      repro params: every case validates and solves with `loading_ok` True and energy met
      (fails before the fix)
- [x] Same sweep for a hybrid seed's BESS fleet passes
- [x] Summary carries `max_station_loading`; a drawn BESS fleet with a partial station reports
      it above `fleet_loading`
- [x] Overload warning and compliance reason quote the worst station, with the fleet average as
      context; frontend compliance test covers it
- [x] Golden baseline refreshed; differences are only the new key and message text, listed
- [x] Full Python and frontend suites, build and lint pass

## Comments

**Bug 1 (seed).** `_size_bess_fleet` in `backend/seed.py` now computes
`required = max(required_energy, required_loading)` after the fixed-point loop, where
`required_loading = ceil(stage1.s_inv_kva * maximum / station_limit)` — `station_limit` was
already a local (`station.rating_at(ambient) * max_loading`), reused rather than recomputed.
Station-count derivation and `_bess_containers` fill are unchanged; `_seed_hybrid` gets the fix
for free since it calls the same helper.

Pre-fix sweep (`tests/test_seed_bess.py`, HV/132kV, pf 0.95, SUNGROW_MVS7400_LS,
max_loading_bess 0.8, trunk 800 m, spacing 350 m, aux 120 kW/40 kvar) failed at exactly the MW
values the ticket names: 25, 30, 35, 45, 50 (`loading_ok` False); 20, 40, 60 passed. Post-fix,
all 8 values pass. Container counts, old -> new (extra containers from the loading floor):
20: 16->16 (+0), 25: 19->20 (+1), 30: 22->24 (+2), 35: 25->28 (+3), 40: 32->32 (+0),
45: 35->36 (+1), 50: 37->39 (+2), 60: 47->47 (+0).

The same sweep against a hybrid seed's BESS fleet (`tests/test_seed_hybrid.py`, base
`BASE_PARAMS`, MV interconnection, `GENERIC_BESS_TX_4000_LV069`/`sungrow-st6900ux-4h`) already
passed for all 8 values before the fix — that pairing/voltage combination doesn't happen to hit
the partial-station case in this parameter range. The test still stands as a regression guard
for the shared helper, per the ticket's ask.

**Bug 2 (messages).** Added `PlantLayout.max_station_loading` (read-only property, the max
`plan.loading` across `circuit_plans`) in `powertool/architecture.py` so it survives
`dataclasses.replace()` unchanged. Added `"max_station_loading"` to the nested per-branch dict
in `powertool/graph.py::branches_summary` only — the flat single-fleet `summary` dict (the
golden-snapshot-pinned byte-identical path) is untouched. Rewrote both PV and BESS
`fleet_overloaded` branches into one shared message: "The {PV|BESS} fleet is overloaded — its
most loaded station is at N% against an M% maximum (fleet average P%). Add stations or pick
bigger units." — kept the trailing suggestion. Dropped the stale "BESS allocation remains
proportional to transformer rating" comment. Mirrored in `frontend/src/compliance.ts`'s
`fleetReasons` and `frontend/src/types.ts`'s `BranchSummary`.

**Golden baseline.** Regenerated via `python -m tests.golden_snapshot`. `git diff` shows exactly:
the new `max_station_loading` key added to every branch entry (14 additions across the fixture
set), and the `fleet_overloaded` message text changed on the 6 already-overloaded pinned cases
(3 BESS wording, 2 PV wording, matching duplicated case appearing twice). No other field or
numeric value changed — confirmed by diffing with both `max_station_loading` and `"message"`
lines filtered out (empty result).

**Tests changed (existing assertions).**
- `frontend/src/compliance.test.ts`: added `max_station_loading: 0.83` to the `fleet()` fixture
  default (new required field). `'fails on an overloaded fleet'` now sets an explicit
  `max_station_loading: 1.2` distinct from `fleet_loading: 1.14` and asserts both `'120%'` and
  `'114%'` appear, so it actually exercises the new wording instead of incidentally matching on
  the average. Same treatment for `'names the fleet whose loading failed...'`
  (`max_station_loading: 1.5`, asserts `'150'`, `'90'`, `'140'`). No other assertions changed;
  `tests/test_graph.py` has no test asserting the old `fleet_overloaded` message text (only a
  code-membership check), so nothing there needed updating.

**Verification.** `.venv/bin/python -m pytest -q` -> 444 passed. Frontend
`DATABASE_URL=... npx vitest run` -> 15 files, 151 passed. `npm run build` -> succeeds (pre-existing
>500kB chunk-size advisory only). `npm run lint` -> 0 errors, 5 pre-existing warnings unrelated
to this change (Modal.tsx fast-refresh, two setState-in-effect warnings).

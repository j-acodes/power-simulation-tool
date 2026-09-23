# 05: PV seed counts stations against the maximum-loading limit

**What to build:** The PV-only seed sizes its station count from installed inverter capacity
alone and never checks the transformer station's rating against the maximum-loading limit. With
the wizard's defaults (45 MW, pf 0.95, HV 132 kV, MV 20 kV, 3200 kVA Sungrow station,
SG350HX-20 × 10, max loading 0.8, trunk 800 m, spacing 350 m, aux 120 kW / 40 kvar) the proposal
solves NOT COMPLIANT: fleet loading 97 % against an 80 % limit. This bug is on `main` too; it
predates this feature. BESS got the same fix in ticket 02 (commit 06433fa); hybrid avoids it by
iterating on the real solve. The owner approved fixing it here on 2026-09-23, overriding the spec's
"Changing the PV seed's behaviour for PV-only designs" out-of-scope line for this one defect.

**Key interfaces:**
- `_size_pv_fleet` / `_seed_pv` in `backend/seed.py` (the PV count's fixed point on
  `per_station_capacity`). Mirror `_size_bess_fleet`'s `station_limit`:
  `station_limit = station.rating_at(DEFAULT_AMBIENT_C) * max_loading`; add
  `math.ceil((p_poc_kw / pf_target) / station_limit)` to the initial `n = max(...)` and
  `math.ceil(stage1.s_inv_kva / station_limit)` to the loop's `next_n = max(...)`. The engine's
  fleet loading is `hypot(p_inv, q_inv) / (n * rating_at(ambient))`.
- Hybrid calls the same PV sizing; its real-solve iteration stays and should now rarely bump.
- `tests/test_seed.py` uses `max_loading: 1.0` in its reference params, which hides the bug.
  Existing assertions whose station counts legitimately change may be updated, each with a
  one-line reason. Add a test that fails first using the repro above.
- The golden baseline's seeded cases (`seed_45mw_hv`, `seed_45mw_mv`, `seed_10mw_hv`,
  `seed_120mw_hv`, `max_loading=0.9`) will shift. Regenerate with the repo's mechanism; list each
  changed case with old → new station count and fleet loading. Non-seed cases must not change.

**Blocked by:** 04: Cutover, baseline and docs.

**Status:** done

- [x] The repro parameters seed a PV diagram that validates and solves with loading within 0.8
- [x] A PV seed whose inverter-sized count already fits the limit is unchanged
- [x] BESS and hybrid seed tests pass unmodified
- [x] Golden baseline refreshed; only the seeded PV cases (and hybrid, if any) differ, each explained
- [x] Full Python and frontend suites and type checks pass

## Comments

Fixed by mirroring `_size_bess_fleet`'s `station_limit` in `_size_pv_fleet`
(`backend/seed.py`): `station_limit = station.rating_at(DEFAULT_AMBIENT_C) *
max_loading`, added as a fourth term to both the initial `n = max(...)` and the
loop's `next_n = max(...)`.

Added `test_max_loading_bounds_the_pv_station_count` in `tests/test_seed.py`
using the ticket's repro params (45 MW, pf 0.95, HV 132/MV 20, SUNGROW_MVS3200,
SG350HX-20 × 10, max_loading 0.8, trunk 800 m, spacing 350 m, aux 120 kW /
40 kvar). Confirmed it fails on the unfixed code (`loading_ok` False) before
the change, and passes after.

No existing `tests/test_seed.py` assertions changed — `REFERENCE_PARAMS` and
its derivatives all use `max_loading: 1.0`, where `station_limit` never
binds, so every existing station-count assertion is unaffected.

Golden baseline (`tests/golden_baseline.json`, all at `max_loading=0.9`):

| case | stations old → new | fleet_loading old → new | loading_ok old → new |
| --- | --- | --- | --- |
| `seed_45mw_hv` | 12 → 14 | 0.9799 → 0.8341 | False → True |
| `seed_45mw_mv` | 12 → 13 | 0.9204 → 0.8472 | False → True |
| `seed_10mw_hv` | 3 → 3 (unchanged) | 0.8750 → 0.8750 (unchanged) | True → True |
| `seed_120mw_hv` | 32 → 35 | 0.9655 → 0.8793 | False → True |

`seed_10mw_hv`'s inverter-sized count already met the limit, so its baseline
entry is byte-identical — the criterion this ticket asked to prove. No
non-seed case (1-4, 9-14) or the hybrid case (14) differs; confirmed by a
key-by-key diff of the old and new baseline JSON.

Verification: `.venv/bin/python -m pytest -q` → 428 passed. From `frontend/`:
`DATABASE_URL=... npx vitest run` → 151 passed (15 files); `npm run build` →
succeeds; `npm run lint` → only pre-existing warnings (`Modal.tsx`,
`DesignEditorPage.tsx`, `Stage1Page.tsx`), no errors, none in files this
ticket touched.

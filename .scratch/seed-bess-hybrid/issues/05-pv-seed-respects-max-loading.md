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

**Status:** ready-for-agent

- [ ] The repro parameters seed a PV diagram that validates and solves with loading within 0.8
- [ ] A PV seed whose inverter-sized count already fits the limit is unchanged
- [ ] BESS and hybrid seed tests pass unmodified
- [ ] Golden baseline refreshed; only the seeded PV cases (and hybrid, if any) differ, each explained
- [ ] Full Python and frontend suites and type checks pass

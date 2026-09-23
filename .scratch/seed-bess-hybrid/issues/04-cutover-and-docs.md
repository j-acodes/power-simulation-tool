# 04: Cutover, baseline and docs

**What to build:** The golden baseline is refreshed for the BESS/hybrid numbers that ADR-0008
shifts, with each changed case explained. The CTO-Demo rebuild script still produces a valid,
solving project. Project status documentation records BESS and hybrid seeding and PCS-governed
allocation. A database reset, if needed, happens only with the owner's explicit authorization.

**Blocked by:** 03: Seed a hybrid plant.

**Status:** done

- [x] Golden baseline refreshed; only BESS/hybrid cases differ, each difference explained
- [x] CTO-Demo rebuild script runs against a disposable database and the project solves
- [x] Project status documentation updated
- [x] Full Python and frontend test suites and type checks pass
- [x] One real-browser check per technology (PV, BESS, hybrid) seeding from the wizard (coordinator)

## Comments

Golden baseline regenerated (`.venv/bin/python -m tests.golden_snapshot`). Diffed old vs new
before regenerating: 53 leaf differences, every one inside a BESS or hybrid case
(`bess_3mw_4h_tx2750`, `bess_3mw_4h_tx4000`, `bess_12mw_4h_tx4000`, `bess_3mw_no_duration`,
`bess_3mw_4h_override_1`, `hybrid_pv_and_bess_3mw_4h`); cases 1-8 (all PV-only) and the
zero-BESS-target hybrid gate (covered separately by `test_hybrid.py`) are untouched. No
previously-asserted value changed — every diff is either:

- eight new keys added to each BESS station's node payload (`pcs_model`, `pcs_unit_count`,
  `pcs_unit_power_kva`, `pcs_capacity_kw`, `pcs_active_loading`, `pcs_apparent_loading`,
  `pcs_active_ok`, `pcs_apparent_ok`) — the PCS loading check ADR-0008 adds to every BESS
  station, independent of whether that station's allocated duty changed; or
- the `results.warnings` list growing by 2 entries (`pcs_active_capacity_exceeded` and
  `pcs_apparent_capacity_exceeded`) on every fixture whose single station's installed PCS
  (pairing-maximum containers × PCS units × PCS kVA) is smaller than the duty it is asked to
  carry — true of every `_bess_only` fixture at 3 MW or 12 MW against the small pairings these
  fixtures use (`GENERIC_BESS_TX_2750_LV069`/`_4000_LV069` paired to `sungrow-st6900ux-4h`),
  except `bess_3mw_4h_tx4000` (8 PCS units × 450 kVA = 3600 kW covers 3 MW, `pcs_active_ok`/
  `pcs_apparent_ok` both `True`, no new warning).

Every changed fixture is single-station-per-branch (`_bess_only`, and the one BESS station in
`_hybrid_with_drawn_bess`), so proportional-by-PCS allocation still routes 100% of the branch's
duty to that one station — identical to the old transformer-rating allocation. Nothing here
exercises multi-station proportional splitting (no golden fixture draws more than one BESS
station); that path is covered by `tests/test_hybrid.py`'s ticket-01 unit tests instead.

CTO-Demo (`.scratch/cto-demo/build_demo_project.py`) needed no changes: it sends `technology`
implicitly as `"pv"` (the default) and hand-swaps node `props` to a full-pairing BESS station
after seeding, so it never exercises the new BESS/hybrid seed request fields. Ran against a
disposable `DATABASE_URL` and a local uvicorn on port 8901 (not 8000) with `--save`: all three
designs (PV 50 MW, BESS 25 MW / 100 MWh, Hybrid PV 50 MW + BESS 25 MW) solved with zero issues
— the full-pairing BESS stations it seeds don't trip the new PCS warning.

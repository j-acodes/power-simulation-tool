# 02: Check each station's through current against its own switchgear

**What to build:** a design tells the engineer whether every station's MV switchgear can carry
what its circuit puts through it. Each station is checked against its **through current** — its
own current plus that of every station downstream of it in the chain — so the station nearest
the busbar, carrying the most, is usually the one that binds.

Two failures behave differently. A station whose own current alone exceeds its own rating stops
the solve with a descriptive error, because the catalogue contradicts itself and nothing
downstream of it is trustworthy. A circuit that is collectively too heavy still solves and still
reports every current, flagged non-compliant, with the offending station identified by node so
the editor can select it — the engineer needs those numbers to know where to split.

The flat 400 A cap is still in place and still does the grouping. This ticket adds the real
check beside it without changing any existing number.

**Blocked by:** 01.

**Status:** resolved

- [ ] Every station carries a through current in the results, alongside the switchgear rated
      current it was checked against.
- [ ] No utilization factor is applied; the limit is the rating itself.
- [ ] A station over its own rating on its own current raises a descriptive error in the style
      of the existing "No cable can carry…" error.
- [ ] A circuit over the limit collectively returns full results, is non-compliant, and emits a
      graph issue carrying the offending station's node id.
- [ ] Covered at the `solve_graph` seam in `tests/test_graph.py`, following
      `test_pv_inverter_capacity_and_power_factor_violations_warn_but_return_results`.
- [ ] The check reads the through current the segment walk already computes rather than
      recomputing it.
- [ ] `golden_baseline.json` is unchanged — no existing design's numbers move.

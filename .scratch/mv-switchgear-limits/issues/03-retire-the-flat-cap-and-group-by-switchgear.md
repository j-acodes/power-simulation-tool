# 03: Retire the 400 A cap and let switchgear decide circuit size

**What to build:** circuit grouping is driven by the engineer's hardware instead of a retired
default. The flat `max_circuit_current_a` setting is deleted outright — rule default, rule
reader, layout object, solve inputs, API schemas, seed parameters, the interface control and the
PDF report. A saved design still carrying the key in `settings.rules` ignores it rather than
failing.

Grouping stops bin-packing against a scalar. A grouping is admissible when, at every position in
every circuit, the accumulated through current is within that position's station's switchgear
rated current. Stage-1 planning keeps its biggest-station-nearest ordering and may reorder to
satisfy the constraint. A drawn diagram keeps the order it was drawn in and is only checked,
never rearranged.

This is where every number moves. Expect fewer, heavier circuits and trunk segments resolving to
parallel cables.

**Blocked by:** 02.

**Status:** ready-for-agent

- [ ] `max_circuit_current_a` exists nowhere in the engine, backend, frontend, seed or report.
- [ ] A saved design carrying the key solves and ignores it.
- [ ] Grouping satisfies the per-position through-current constraint, not a scalar cap.
- [ ] Stage-1 planning may reorder; `test_manual_arrangement_never_reorders_what_was_drawn`
      still passes unmodified.
- [ ] The `test_assign_*` family is rewritten to assert per-position switchgear semantics.
- [ ] The compliance verdict's "all circuits under cap" clause reads "every station within its
      switchgear rated current".
- [ ] **Before** regenerating the baseline: one design's expected circuit count and trunk
      through current are computed by hand and pinned as their own test, and that test passes.
- [ ] `golden_baseline.json` is regenerated only after the anchor passes, and the diff is
      reported rather than silently accepted.
- [ ] The database is reset per the project's established workflow, since a settings key was
      removed.

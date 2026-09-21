# Spec: Switchgear rated current bounds a circuit

**Status:** tickets 01–02 shipped; 03–04 superseded by `.scratch/switchgear-model/spec.md` (ADR-0007).

## Problem Statement

An engineer drawing a plant has no way to find out whether the MV switchgear inside their
transformer stations can actually carry the current the circuit puts through it. The tool never
looks: the switchgear rated current is transcribed into the catalogue and shown in the
specification view, but the sizing engine has never read it.

In its place the tool applies a flat 400 A cap to every circuit in every design. That number
came from a sidebar in a retired application. It is not a property of any equipment, it does not
change with voltage, cable or station model, and nothing in the interface tells the engineer
that the circuit sizes they are being shown were decided by a default rather than by their
hardware. A design can therefore be reported compliant while calling for switchgear that cannot
carry its own circuit, and can equally be split into more circuits than the hardware needs.

## Solution

A circuit is bounded by the switchgear of the stations in it.

Each station is checked against its **through current** — its own current plus that of every
station downstream of it in the chain — and must stay within its own **switchgear rated
current**. The station nearest the busbar carries the most, so the limit binds per station at a
position, not per circuit as a whole. The flat 400 A cap is deleted: field, default, interface
control and saved setting.

When a supplier has not published a rating, the design falls back to the standard 630 A
ring-main-unit size and tells the engineer it did so, rather than treating the silence as the
absence of a limit.

Two failures are distinguished. A station whose own current alone exceeds its own rating is a
hard error — the catalogue contradicts itself. A circuit that is collectively too heavy solves
and reports its currents, flagged non-compliant, so the engineer can see where to split it.

## User Stories

1. As a design engineer, I want each station checked against its own switchgear rated current,
   so that a compliant design is one I can actually build.
2. As a design engineer, I want the current each station passes toward the busbar shown per
   station, so that I can see which station in a circuit is the constrained one.
3. As a design engineer, I want the station nearest the busbar understood to carry the whole
   circuit's current, so that the check matches how a daisy chain actually behaves.
4. As a design engineer, I want a circuit that exceeds its stations' switchgear to still solve
   and report its numbers, so that I can see how far over it is and where to split it.
5. As a design engineer, I want the offending station identified by name when a circuit is over,
   so that I do not have to work out which one bound it.
6. As a design engineer, I want a station whose own current alone exceeds its own rating to stop
   the solve outright, so that I am never shown numbers derived from a self-contradictory
   catalogue entry.
7. As a design engineer, I want circuit grouping driven by the switchgear of my chosen stations,
   so that I am not given more circuits than my hardware requires.
8. As a design engineer, I want no arbitrary current cap applied to my design, so that the
   circuit count I am shown reflects equipment rather than a retired default.
9. As a design engineer using Huawei JUPITER stations, I want a clear notice that no switchgear
   rating is published and a stated fallback was used, so that I know to obtain the real figure
   before a design review.
10. As a design engineer, I want the fallback never to mean "unlimited", so that a supplier's
    silence cannot quietly remove a limit from my design.
11. As a design engineer, I want the switchgear rated current shown in the specification view
    marked as a figure the engine now reads, so that I know it carries design-review weight.
12. As a design engineer, I want the switchgear limit applied without a utilization factor, so
    that my stations are not silently derated by a margin meant for buried cable.
13. As a design engineer planning from Stage 1, I want the planner to order stations so the
    switchgear limit is satisfied where it can be, so that I get a workable starting layout.
14. As a design engineer, I want my drawn diagram never silently rearranged, so that the canvas
    keeps meaning what I drew.
15. As a design engineer, I want the compliance verdict to state that every station is within
    its switchgear rating, so that the verdict's wording matches what was actually checked.
16. As a design engineer, I want the PDF report to show each station's through current against
    its rating, so that the report carries the evidence for the verdict.
17. As a design engineer with an existing saved design, I want the removal of the old cap to be
    explicit rather than silent, so that I understand why my circuit counts changed.
18. As a design engineer, I want trunk segments that now need parallel cables to be sized and
    labelled as such, so that heavier circuits do not hide a cable problem.
19. As a maintainer, I want the switchgear rated current to sit in the simulated tier, so that
    the catalogue's own vocabulary tells me it is read by the engine.
20. As a maintainer, I want the 630 A fallback to live in the engine and not in the YAML, so
    that a number in a station's datasheet block always means a supplier published it.

## Implementation Decisions

- `rmu_rated_current_a` moves from the typed tier to the simulated tier on the transformer
  station component. It keeps its name in the data files; the domain term for it in prose,
  results and interface copy is **switchgear rated current**. The rest of the RMU block
  (`rmu_units`, `rmu_relay_protection`, `rmu_short_time_withstand`, `rmu_kv_min`, `rmu_kv_max`)
  stays typed.
- The rating is a single figure with no ambient dimension, deliberately diverging from the
  per-ambient shape used for AC power at ambient and inverter power at ambient. Recorded in
  ADR-0006: no supplier publishes a second figure, and three of the catalogue's stations do not
  publish the first.
- No utilization factor is applied. The cable `max_utilization` setting keeps its current
  meaning and applies only to cables.
- An unpublished rating resolves to 630 A and raises a notice naming the station and the
  fallback. The constant lives in the engine, not in the YAML.
- `max_circuit_current_a` is deleted from the rule defaults, the rule reader, the layout object,
  the solve inputs, the API schemas, the seed parameters, the interface settings control and the
  PDF report. A saved design carrying the key in `settings.rules` ignores it rather than failing.
- Circuit grouping stops bin-packing against a scalar cap. A grouping is admissible when, at
  every position in every circuit, the accumulated through current is within that position's
  station's switchgear rated current. Stage-1 planning keeps its existing biggest-station-nearest
  ordering and may reorder to satisfy the constraint; the drawn-diagram path keeps the given
  order and only checks it.
- The per-station through current is already computed by the segment walk that sizes cables; the
  check reads that quantity rather than recomputing it.
- Compliance gains a per-station switchgear check. The existing circuit-level `current_ok` flag
  is replaced by the per-station result. The approved compliance criteria's "all circuits under
  cap" clause becomes "every station within its switchgear rated current".
- A station whose own current alone exceeds its own rating raises a descriptive error in the
  same style as the existing "No cable can carry…" error. A circuit over the limit collectively
  produces a graph issue pointing at the offending station's node, so the editor can select it.
- Results, specification view and PDF report show each station's through current alongside its
  switchgear rated current, and mark a fallback-sourced rating as such.
- Deleting a settings key is a schema change, so the database is reset per the project's
  established workflow. It is empty at the time of writing, so nothing is lost.

## Testing Decisions

A good test here asserts external behaviour: what a design reports, what it refuses, what the
catalogue resolves to. It does not assert the shape of intermediate structures. Prefer the
highest seam that can see the behaviour.

Three existing seams, no new ones:

- **`solve_graph`, tested in `tests/test_graph.py`** — the highest seam and the primary one. A
  too-heavy circuit reporting results while flagging the offending station, and a
  self-contradictory station refusing to solve, are both visible here. Prior art:
  `test_pv_inverter_capacity_and_power_factor_violations_warn_but_return_results`.
- **`powertool/architecture.py`, tested in `tests/test_architecture.py`** — grouping and the
  segment walk. The existing `test_assign_*` family asserts scalar-cap semantics and is rewritten
  to assert per-position switchgear semantics. `test_segment_loading_cumulative_and_decreasing`
  and `test_manual_arrangement_never_reorders_what_was_drawn` already pin behaviour this work
  must preserve.
- **Catalogue load, tested in `tests/test_catalogue.py`** — the 630 A fallback and its notice.
  Prior art is near-exact: `test_missing_30c_inverter_power_falls_back_to_40c_with_notice`.

`tests/golden_baseline.json` is the regression net but cannot validate this change on its own,
because the change moves every number in it on purpose. Before the baseline is regenerated, one
design's expected circuit count and trunk through current are computed by hand and pinned as an
explicit test. The baseline is regenerated only after that anchor passes.

## Out of Scope

- **Cable ampacity derating for installation conditions.** The catalogue's ratings assume direct
  burial, single circuit, soil ~1.0 K·m/W, and real trenches derate from there. The 0.80
  utilization factor is a design margin and is not a derating factor. Whether those are doing
  each other's job is a real question and its own unit of work.
- **Short-circuit and short-time withstand.** `rmu_short_time_withstand` stays typed. Fault-level
  modelling is not part of this.
- **An ambient dimension on the switchgear rated current.** Deliberately deferred, ADR-0006.
- **A margin or derating setting for switchgear.** Not invented before there is a reason to want
  one.
- **Obtaining Huawei's published switchgear rated current.** An owner action against the
  supplier, not something to infer.
- **Any change to cable selection itself.** Per-segment sizing, the loss budget and parallel-run
  behaviour are unchanged; heavier circuits simply exercise them harder.

## Further Notes

Expect circuit sizes to grow by roughly 57% at 20 kV as the bound moves from 400 A (~13.9 MVA) to
630 A (~21.8 MVA), producing fewer and heavier circuits. Cable ampacity will not restrain this:
the largest MV cable in the catalogue is 600 A and the selector adds parallel runs rather than
refusing, so trunk segments commonly resolve to two parallel cables. This is expected, not a
defect, and it is the reason the hand-computed anchor exists.

All five Sungrow MVS PV stations and both real BESS stations inherit 630 A. All three Huawei
JUPITER stations publish nothing and will exercise the fallback on every design that uses them,
which makes the fallback path a primary case rather than an edge case.

Glossary entries **Switchgear rated current** and **Through current** were added during
grilling, and the **Circuit** and **Transformer station** entries were corrected — both had
become false. ADR-0006 records the decision.

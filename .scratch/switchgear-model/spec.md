# Spec: Model the MV switchgear at both ends of every circuit

**Status:** needs-triage — spec agreed in grilling 2026-09-21; not yet split into tickets.
**Supersedes:** tickets 03 and 04 of `.scratch/mv-switchgear-limits/` (tickets 01–02 shipped).
**Decision record:** ADR-0007, amending ADR-0001 and ADR-0006.

## Problem Statement

The tool checks each transformer station's switchgear, but the rest of the MV switchgear in the
plant does not exist in the model. The busbar is a point with no rating, so nothing tells the
engineer what switchboard, feeders or export switchgear the design needs. Cable selection adds
up to twelve parallel runs to a circuit segment without asking whether the switchgear at either
end can terminate them. A flat 400 A circuit cap, derived from no equipment, still decides how
stations are grouped. And a fleet can have only one busbar, so a plant built with two
switchboards cannot be drawn as built.

## Solution

Every circuit is bounded by real switchgear at both ends:

- Each station's **switchgear rated current** is checked against its through current
  (unchanged from ADR-0006; 630 A fallback with a notice).
- Each station declares a **cable entry** — cables per phase and maximum cross-section — with a
  2 × 630 mm² engine fallback and a notice. Every circuit cable must fit the stricter cable entry
  of its two ends.
- Each busbar carries **busbar switchgear** — the busbar, one **feeder** per circuit, and the
  **export switchgear** — sized by the tool to the smallest standard rating that carries its
  design-point current, or pinned by the engineer and checked.
- A fleet may have **several busbars** in parallel, all exporting into the shared HV
  transformer, or into the point of connection for an MV interconnection.
- The flat 400 A cap is deleted.

The engineer sees the sized switchgear, the limit that decided each circuit's size, and every
fallback that was used.

## User Stories

1. As a design engineer, I want the busbar, each feeder and the export switchgear sized for me,
   so that the design tells me what switchboard to specify.
2. As a design engineer, I want sized ratings drawn from standard switchgear sizes, so that the
   result is something I can buy.
3. As a design engineer, I want to pin a switchgear rating I already know, so that the design is
   checked against the equipment I have, not the equipment I would pick.
4. As a design engineer, I want a pinned rating that is too small to be flagged while the design
   still solves, so that I can see by how much it is short.
5. As a design engineer, I want every circuit cable to fit the switchgear terminals at both of
   its ends, so that no segment calls for more or larger cables than can be connected.
6. As a design engineer, I want a station whose supplier publishes no cable entry to fall back
   to two 630 mm² cables and say so, so that I know to confirm the real figure.
7. As a design engineer, I want a segment that no admissible cable can carry to be flagged at
   that segment rather than stopping the solve, so that I can see where to split the circuit.
8. As a design engineer, I want circuit grouping decided by my equipment and not by a flat
   current cap, so that circuit counts reflect what I drew.
9. As a design engineer, I want to draw more than one busbar for a fleet, so that I can model a
   plant with several switchboards as it will be built.
10. As a design engineer planning from Stage 1, I want another busbar opened when one would
    exceed 4000 A or 12 feeders, so that the plan is buildable.
11. As a design engineer, I want my drawn diagram never rearranged between busbars, so that the
    canvas keeps meaning what I drew.
12. As a design engineer with a hybrid design, I want each fleet's busbars sized and checked on
    their own, so that PV and BESS switchgear are not confused.
13. As a design engineer, I want to see, per circuit, which limit decided its size — station
    switchgear, feeder, cable entry or feeder count — so that I know what to change to enlarge it.
14. As a design engineer, I want the PDF report to carry the sized switchgear and the per-station
    checks, so that the report is the evidence for the verdict.
15. As a design engineer, I want the export cable to keep using as many parallel runs as it
    needs, so that a large busbar is not reported as unbuildable.
16. As a maintainer, I want cable entry in the simulated tier, so that the catalogue vocabulary
    says the engine reads it.
17. As a maintainer, I want the cable-entry and switchgear fallbacks to live in the engine, not
    the YAML, so that a figure in a datasheet block always means a supplier published it.

## Implementation Decisions

- **Station switchgear** stays as shipped in tickets 01–02: `rmu_rated_current_a`, simulated,
  630 A engine fallback, checked against through current, no utilization factor.
- **Cable entry** adds two simulated parameters to the transformer station component: cables
  accepted per phase (integer) and maximum cable cross-section (mm²). The fallback of 2 and
  630 mm² is an engine constant, raised with a notice naming the station. One cable entry per
  station model, applied to incoming and outgoing cables alike.
- **Cable selection** for a circuit segment takes a per-segment bound: the parallel-run limit is
  the lesser of the two ends' cables per phase, and candidates above the lesser maximum
  cross-section are excluded. Export cables keep today's `max_parallel` behaviour. The feeder's
  cable entry is 2 × 630 mm² — the busbar switchgear is sized, so there is no published figure.
- **Busbar switchgear** is sized per busbar: each feeder against its circuit's head current, and
  the busbar and export switchgear against the busbar total including auxiliary load, all at the
  design point. Standard ladder: 630, 800, 1250, 1600, 2000, 2500, 3150, 4000 A. Smallest rating
  ≥ current, no margin. A current above 4000 A has no admissible size and is flagged.
- **Pins** are optional per-busbar values in diagram JSON: one for the busbar, one for the export
  switchgear, one per feeder. A pinned value is checked, never resized.
- **Several busbars per fleet**: the validator drops the one-busbar-per-kind rule and keeps the
  kind-mismatch rule. Each busbar is its own branch feeding the shared HV transformer (or the POC);
  the export cascade sums the busbars. Loading and the reactive split stay per fleet, not per
  busbar. Auxiliary load attaches to the busbar its node or its stations are drawn against.
- **Stage-1 planning** keeps biggest-station-nearest ordering, groups stations so every station
  is within its switchgear rated current and every segment has an admissible cable, and opens a
  new busbar when the next circuit would take the current one past 4000 A or past the
  feeders-per-busbar limit. That limit is a design setting defaulting to 12.
- **The flat cap** `max_circuit_current_a` is deleted everywhere, as ticket 03 specified: rule
  defaults, rule reader, layout, solve inputs, API schemas, seed parameters, settings control and
  PDF. A saved design carrying the key ignores it.
- **Failures** follow ADR-0006. Hard error: a station whose own current alone exceeds its own
  switchgear rated current, or which no cable within its own cable entry can carry. Solve and
  flag, pointing at the offending node or edge: a station over its rating by through current, a
  segment with no admissible cable, a pinned rating too small, a busbar over 4000 A.
- **Display**: the busbar inspector shows each sized or pinned rating, marked as which, beside
  its current. Results show per circuit the binding limit, one of: station switchgear, feeder,
  cable entry, feeders per busbar. The specification view marks cable entry as simulated. The
  PDF carries all of it. Each fallback raises a notice.
- **Schema change**: diagram JSON and settings both change, so the database is reset at ship
  time, after inspecting it and confirming with the owner.

## Testing Decisions

Assert what a design reports, refuses or resolves to, at the highest seam that can see it. The
existing seams suffice:

- **`solve_graph`** (graph tests) — primary. Flagged-but-solved cases, hard errors, several
  busbars per fleet, pinned ratings, binding limit per circuit.
- **Architecture** (grouping, segment walk, busbar sizing, Stage-1 busbar opening). The
  `test_assign_*` family is rewritten from scalar-cap semantics.
- **Cable sizing** — the per-segment bound on parallel runs and cross-section.
- **Catalogue load** — the cable-entry fallback and its notice.
- **Frontend Vitest** — inspector display, multiple busbars of one kind accepted by the palette
  and validator.

`tests/golden_baseline.json` moves on purpose. Before regenerating it, hand-compute and pin one
design's circuit count, trunk current, feeder and busbar sizes as an explicit anchor test. Keep
the ADR-0001 golden: a hybrid design with zero BESS power reproduces the PV-only result.

## Out of Scope

- Short-circuit and short-time withstand of any switchgear.
- HV-side switchgear of an HV interconnection.
- One HV transformer per busbar; bus-coupled busbar sections.
- Installation derating of cable ampacity.
- A utilization margin on any switchgear rating.
- Obtaining unpublished supplier figures (Huawei switchgear rating, cable entry for any station).

## Further Notes

With 630 A stations and a 2 × 630 mm² entry (960 A usable at 0.80 utilization), the station
switchgear binds first on today's catalogue: ~21.8 MVA at 20 kV, ~32.7 MVA at 30 kV per circuit.
The owner reviewed the earlier ~400 A expectation and accepted 630 A as the standard. Cable
entry becomes the binding limit only when a station publishes a smaller one.

Whether any on-file datasheet publishes cable entry was not checked in the grilling session;
check before the catalogue ticket.

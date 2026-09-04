# Spec: PV/BESS station separation and BESS sizing

Status: ready-for-agent

## Problem Statement

The tool sizes PV plants only. Every station a user can draw is, underneath, just a
transformer — there is no way to say "this station is a battery". The one transformer
catalogue is explicitly for PV string-inverter stations, the default LV bus is the PV
string-inverter voltage, the Stage-1 entry point is named for PV inverters, and the PDF
report is headed "PV Plant".

A sizing engineer working on a battery project therefore cannot use the tool at all. They
cannot record which supplier solution a station uses, how many containers sit behind it,
what energy the plant delivers, or whether that energy meets the project's discharge
duration. They also cannot draw a project that has both PV and batteries behind one grid
connection, which is an increasingly common arrangement.

Underneath the missing features is a modelling gap: because a station carries no kind, the
engine spreads inverter power across *every* drawn station at uniform per-unit loading. Two
different asset classes on one canvas would silently smear PV power onto battery stations
and back, producing plausible numbers that are wrong.

## Solution

A station gains a **kind** — `pv` or `bess` — and the model gains the concepts that hang off
it: a BESS solution chosen from a catalogue, containers behind each station, a discharge
duration for the project, and an energy compliance check alongside the existing loading
check.

A sizing engineer can now draw a battery plant the same way they draw a PV plant: set the
power at the point of connection, pick a supplier solution and a discharge duration, and get
apparent, active and reactive power at PCS level through the full loss chain, together with
station and container counts and a pass/fail on both loading and delivered energy.

They can also draw a **hybrid** plant: one point of connection carrying a PV power figure
and a BESS power figure, a shared HV transformer sized on the combined requirement, and one
MV busbar per fleet below it. Each fleet is sized as its own independent cascade, so neither
asset class distorts the other. The reactive duty required at the point of connection is
split between the two fleets by an explicit share the engineer controls.

Existing PV designs keep working unchanged and produce identical numbers.

## User Stories

1. As a sizing engineer, I want to mark a station as PV or BESS, so that the tool knows
   which physical asset I am modelling.
2. As a sizing engineer, I want stations to default to PV when a design does not say
   otherwise, so that every design I saved before this feature still opens and solves.
3. As a sizing engineer, I want my existing PV designs to produce byte-identical results
   after this change, so that I can trust that nothing silently moved.
4. As a sizing engineer, I want a catalogue of BESS supplier solutions, so that I can pick a
   real product instead of retyping its specification on every project.
5. As a sizing engineer, I want a BESS solution to carry its container energy, PCS power,
   PCS LV voltage and worst-case auxiliary load, so that one selection populates everything
   downstream.
6. As a sizing engineer, I want a separate catalogue of BESS station transformers, so that
   the tool never offers me a PV string-inverter station for a battery.
7. As a sizing engineer, I want the palette to show only the transformers valid for the kind
   of station I am placing, so that I cannot build an invalid design by accident.
8. As a sizing engineer, I want the tool to reject a BESS station whose transformer LV
   voltage disagrees with its solution's PCS voltage, so that a mismatched pairing is caught
   at design time rather than in the results.
9. As a sizing engineer, I want to set the power at the point of connection for a BESS
   project exactly as I do for PV, so that I do not have to learn a second workflow.
10. As a sizing engineer, I want both autosizing and manual sizing available for BESS, so
    that the two asset classes behave consistently.
11. As a sizing engineer, I want to set a discharge duration for the project, so that the
    tool can determine how much energy the plant must deliver.
12. As a sizing engineer, I want the discharge duration restricted to the durations my
    chosen solution actually supports, so that I cannot request a configuration the supplier
    does not sell.
13. As a sizing engineer, I want the number of containers per station to come from the
    supplier's own table, so that the count I present in a design review is defensible.
14. As a sizing engineer, I want the station count to derive from power as it already does
    for PV, so that the sizing logic I already trust is reused.
15. As a sizing engineer, I want to see the total delivered energy of the plant, so that I
    can compare it against what the project requires.
16. As a sizing engineer, I want a design to fail compliance when delivered energy falls
    short of power times duration, so that an undersized plant cannot pass review.
17. As a sizing engineer, I want a design to fail compliance when fleet loading exceeds its
    limit, exactly as it does today, so that the existing gate is preserved.
18. As a sizing engineer, I want separate maximum loading limits for the PV fleet and the
    BESS fleet, so that I can reflect their different duty cycles.
19. As a sizing engineer, I want to see which specific gate failed and by how much, so that
    I know what to change.
20. As a sizing engineer, I want BESS auxiliary load taken from the supplier specification
    at worst case, so that I size against the conservative condition without maintaining a
    load curve.
21. As a sizing engineer, I want auxiliary load aggregated at the MV busbar rather than
    inflating PCS sizing, so that the PCS rating reflects the export duty only.
22. As a sizing engineer, I want PCS power, reactive power and apparent power reported at
    the conversion level for BESS stations, so that I can specify the equipment.
23. As a sizing engineer, I want the conversion device labelled "PCS" on battery stations
    and "inverter" on PV stations, so that the report speaks the language of each asset.
24. As a sizing engineer, I want to draw PV and BESS stations on one canvas, so that I can
    model a hybrid project behind a single grid connection.
25. As a sizing engineer, I want to enter a separate point-of-connection power for each
    fleet, so that the two asset classes are sized to their own targets.
26. As a sizing engineer, I want a single shared HV transformer sized on the combined
    requirement, so that the model matches the single physical grid connection.
27. As a sizing engineer, I want one MV busbar per fleet, so that the separation between the
    two collection systems is explicit on the drawing.
28. As a sizing engineer, I want the tool to reject a station connected to the other fleet's
    busbar, so that a mis-drawn hybrid cannot be solved.
29. As a sizing engineer, I want the tool to reject a second busbar of a kind that already
    exists, so that the one-busbar-per-fleet rule is enforced.
30. As a sizing engineer, I want the power factor target to remain a single requirement at
    the point of connection, so that it continues to describe what the grid operator asks
    for.
31. As a sizing engineer, I want to control how the reactive duty is split between the PV
    and BESS branches, so that I can reflect the reactive strategy agreed for the project.
32. As a sizing engineer, I want the reactive split to default to pro-rata by active power,
    so that the common case needs no extra input.
33. As a sizing engineer, I want the automatic layout to place both busbars and all their
    stations, so that a hybrid drawing arranges itself as cleanly as a single-fleet one.
34. As a sizing engineer, I want a hybrid design with zero BESS power to reproduce the
    PV-only result exactly, so that I can verify the hybrid path against the path I trust.
35. As a sizing engineer, I want the tool to tell me explicitly when the loss refinement
    fails to converge, so that I am never handed a plausible-looking number that is wrong.
36. As a sizing engineer, I want the PDF report to use neutral plant naming, so that a
    battery project's report is not headed "PV Plant".
37. As a sizing engineer, I want the report to include container counts and the energy
    compliance result, so that the document stands alone in a design review.
38. As a developer, I want the Stage-1 entry point named for generation rather than PV, so
    that its name matches what it now does.
39. As a developer, I want the previous entry-point name kept as a deprecated alias, so that
    the public interface does not break without warning.
40. As a developer, I want a reactive-power-in sizing entry point, so that a branch can be
    sized against an assigned reactive duty rather than a power factor it owns.
41. As a developer, I want the branch restructure to land as a pure refactor, so that any
    numerical movement is immediately identifiable as a bug.
42. As a developer, I want a project glossary and an architecture decision record for the
    hybrid topology, so that the reasoning survives this conversation.

## Implementation Decisions

### Domain model

- A station gains a **fleet kind** discriminator with values `pv` and `bess`. It is a
  property of the station, not a class hierarchy — a station remains backed by a transformer.
- Absent kind parses as `pv`. This is the backward-compatibility guarantee for every design
  already saved.
- The station plan and station result value objects both carry the kind, the station's LV
  voltage, and — for BESS — container count and delivered energy.
- **No database migration is required.** The whole diagram is persisted as opaque JSON in
  the designs table, and diagram parsing is already permissive about unknown keys. The
  component catalogue is YAML loaded at startup, not SQL.

### Catalogues

- A new **BESS solution** catalogue, separate from the transformer and cable catalogues and
  loaded by the same component database. The shape, which encodes several decisions at once:

  ```python
  @dataclass(frozen=True)
  class BessSolution:
      name: str
      e_container_kwh: float
      pcs_p_kw: float
      pcs_lv_kv: float
      aux_p_kw: float                          # worst case, from the spec sheet
      aux_q_kvar: float
      containers_by_duration: dict[float, int] # discharge hours -> containers per station
  ```

- A **separate BESS station-transformer catalogue**, not a category field on the existing
  one. The catalogue endpoint exposes both new collections; the palette filters by the kind
  of station being placed.
- Container count per station is read from `containers_by_duration`. It is never
  interpolated, derived or rounded.

### Sizing

- The Stage-1 entry point is renamed from its PV-specific name to a generation-neutral one,
  with the old name retained as a deprecated alias on the public interface.
- A **reactive-in sibling entry point** is added alongside it, taking active and reactive
  power at the head of the chain. The power-factor form computes the reactive figure and
  delegates. This is required because in a hybrid plant a branch's reactive duty is
  *assigned* to it by the split, not derived from a power factor the branch owns.
- LV voltage is **per station**, taken from the station transformer's own rating. This is
  cheaper than it appears: the transformer loss model is expressed in per-unit of rating and
  ignores voltage, and no LV cable is ever sized. LV is therefore a catalogue, validation and
  labelling concern, not a cascade-physics one. The diagram-level LV setting survives only as
  the default for custom transformers.

### Fleet restructure

- Uniform per-unit loading currently spans every drawn station: fleet apparent power is
  summed across all of them and each station takes a share of one Stage-1 result. With two
  fleets this is wrong, and one loading flag cannot express two limits.
- Replacement: **one plant layout per fleet**, each built from its own Stage-1 result and its
  own maximum loading. Uniform per-unit loading survives *within* a fleet unchanged.
- The plant architecture sizing function splits into a per-branch half and a plant-level half.
  The plant-level half takes the branch results and sizes the shared HV transformer and
  export cable once.
- The plant architecture object exposes its branches, and keeps its previous single-fleet
  accessors as compatibility properties delegating to the sole branch when there is one. This
  lets the reporting, PDF and result-mapping layers migrate incrementally.
- The loss-refinement fixed point generalises to per-branch correction scalars summed at the
  shared bus, with the export step applied once.

### Hybrid topology

- The single-busbar rule relaxes to **one busbar per fleet kind**, each carrying its own kind
  and parented by the HV transformer — or by the point of connection when the design uses MV
  interconnection.
- New validation issues replace the old duplicate-busbar error: a duplicate busbar *of the
  same kind*, and a station whose kind disagrees with its busbar. An auxiliary load's parent
  becomes *a* busbar rather than *the* busbar.
- Engine inputs become branch-shaped. Plant-level fields — point of connection, HV, tier
  voltages, rules — stay flat; kind, busbar identity, station identities, circuits, segment
  data, auxiliary totals, maximum loading and the branch's own active and reactive targets
  move into a per-branch structure. The previous flat accessors remain as first-branch
  properties so the result-mapping layer migrates incrementally.
- Point-of-connection properties gain a PV power target, a BESS power target, and a reactive
  share validated into the closed unit interval. The existing single power target remains as
  the PV figure for legacy designs.
- **Solve order**: build the shared export chain, size it on combined power against the
  point-of-connection power factor target to obtain the combined active and reactive
  requirement at the shared MV bus; split that by branch — active pro-rata to each branch's
  target, reactive by the configured share; then per branch build its collection chain, size
  it with the reactive-in entry point, arrange it against its own maximum loading, and size
  its circuits; finally size the shared HV transformer and export once.
- The outer fixed point is **bounded by an explicit iteration cap** that surfaces a
  non-convergence issue rather than returning a plausible number. This follows the existing
  house rule that the engine reports problems as issues the editor can display, never as
  silent garbage.

### Compliance

- Two hard gates for a BESS fleet: fleet loading within its limit, and delivered energy at
  least the branch's point-of-connection power times the discharge duration.
- Delivered energy is container count times container energy, summed across the fleet.
- Discharge duration is a diagram-level setting restricted to the keys of the selected
  solution's duration table. It is rendered as a select so the invalid state cannot be
  expressed in the UI, *and* validated server-side so a hand-edited payload is rejected.
- Maximum loading becomes per kind, with a per-fleet compliance result in the summary.

### Auxiliary load

- Each BESS solution's worst-case auxiliary active and reactive figures are summed across the
  fleet's stations and attached as that branch's lumped busbar auxiliary load.
- This reuses the existing auxiliary load component and auxiliary node kind. No new component
  and no new node kind.
- Auxiliary load enters the cascade below the export step only. It never appears in PCS
  apparent power.

### Presentation

- The conversion-level result fields are **not** renamed or duplicated. The frontend and the
  PDF label them "PCS" when the station kind is BESS and "inverter" when it is PV.
- The API title, the PDF plant-name default and the report footers become asset-neutral.
- The automatic canvas layout currently finds the *first* busbar only, which would silently
  drop the second fleet's stations into the unreached-node fallback. It must place all
  busbars, each with its own row and horizontal band.
- Connection rules gain a check rejecting a station joined to the other fleet's busbar.

### Domain documentation

- Create the project glossary, which does not exist today, covering: station, fleet kind,
  fleet, BESS solution, container, PCS, discharge duration, delivered energy.
- Record an architecture decision for the hybrid topology — shared HV transformer, one busbar
  per fleet, explicit reactive split — which is hard to reverse, surprising without context,
  and the outcome of a genuine trade-off against fully independent connections.

## Testing Decisions

### What makes a good test here

Tests assert **external behaviour through the highest available seam**: a diagram goes in,
issues and results come out. They must not reach into intermediate value objects, per-element
loss breakdowns or private helpers, because the branch restructure deliberately reshapes
those. A test that breaks during a pure refactor is testing the wrong thing.

Numbers are asserted against conservation laws and known-good baselines rather than
transcribed constants wherever possible, consistent with the project's stated principle of
validating against references and checking power balance.

### Seams

Two seams, both already established in the suite — no new seams are introduced.

1. **The top-level solve function** (diagram dict in, issues-and-results dict out) carries
   everything behaviour-bearing: station kind parsing, catalogue selection, per-fleet
   loading, container counts, delivered energy, both compliance gates, auxiliary placement,
   and the hybrid cascade. Prior art: the seed tests already call it directly.
2. **The graph validator** carries the topology rules: one busbar per kind, duplicate-kind
   rejection, station/busbar kind agreement, auxiliary parenting, and unsupported duration.
   Prior art: the graph tests are built almost entirely on this seam.

The catalogue endpoint gets one test for the two new collections, alongside the existing
endpoint tests.

Frontend testing stays on the **existing pure-helper seam** — no jsdom, no testing-library,
no new dependencies. The two things that can silently break are both pure functions: the
automatic layout with two busbars, and the compliance gates. Palette filtering, the duration
select and PCS labelling are verified manually in the running app.

### Specific coverage

- **Regression gate for the branch restructure**: the entire existing suite, unedited, must
  pass. That is the acceptance criterion for that stage — no new tests, no adjusted
  assertions.
- **Golden hybrid test**: a hybrid diagram with zero BESS power reproduces the PV-only result
  to within 1e-9. This is the single most valuable test in the feature.
- **Backward compatibility**: a design with no station kind parses as PV and solves
  identically.
- Container counts at every duration the fixture solution tabulates.
- An energy-shortfall design fails compliance while loading passes, and the converse.
- Auxiliary load appears at the busbar and is absent from PCS apparent power.
- Non-convergence surfaces as an issue rather than a returned result.
- Report tests cover the neutral naming and the BESS sections.

### Commands

```bash
source .venv/bin/activate && pytest
cd frontend && npm test          # vitest
cd frontend && npm run build     # tsc -b && vite build — this is the typecheck
cd frontend && npm run lint      # oxlint
```

## Out of Scope

- **Round-trip efficiency and the cell-to-connection-point efficiency chain.** Named in the
  team brainstorm as a distinct goal and explicitly deferred to its own effort.
- **Charging.** A BESS station is modelled as a generator; only discharge is sized. The
  existing behaviour of recording charging reactive power without netting it in is unchanged.
- **Time series of any kind.** Auxiliary load is a fixed worst-case figure, not a load or
  temperature curve, so nothing in this work introduces a time dimension.
- **Reading inverter parameters from OND files.** A separate item in the brainstorm.
- **The frozen Streamlit reference UI.** Not touched.
- **Interpolating or rounding unsupported discharge durations.** Prevented by construction
  rather than handled.
- **More than one BESS solution per design.** Not prohibited by the model, but not a target
  of this work and not tested.
- **Frontend component or end-to-end test infrastructure.**

## Further Notes

The riskiest part of this work is not the station split — it is the loss-refinement fixed
point once two branches share one HV transformer. Each branch's correction scalar changes the
combined flow, which changes the shared HV loss, which changes both branches' requirements.
The existing code resolves that circularity for exactly one branch. This is also the one code
path with no observable intermediate on the canvas, so an error there is invisible until the
final numbers are wrong. The sequencing — pure refactor first, under an unedited test suite,
then the golden zero-BESS hybrid test, then a bounded iteration with an explicit
non-convergence issue — exists specifically to contain that risk.

A hybrid design is the source of most of the cost and nearly all of the risk in this spec. A
single-kind-per-design model would be roughly half the work. That option was considered and
declined during requirements grilling; it is recorded here only so that a future reader
understands the trade was deliberate.

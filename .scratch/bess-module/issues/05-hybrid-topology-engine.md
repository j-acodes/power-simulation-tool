# 05: Hybrid topology — engine and graph layer

**What to build:** A hybrid plant, authored as a diagram payload, validates and solves
correctly. Drawing one comfortably on the canvas is ticket 06; this ticket makes the
behaviour real and verifiable headless.

A single point of connection carries a power figure per fleet. Below it sits a **shared HV
transformer** sized on the combined requirement, and below that **one MV busbar per fleet**,
each with its own circuits and its own independent cascade. Neither fleet distorts the other.

The single-busbar rule relaxes to one busbar per fleet kind, each declaring its kind and
parented by the HV transformer — or by the point of connection when the design uses MV
interconnection. The old duplicate-busbar error is replaced by narrower ones: a duplicate
busbar *of the same kind*, and a station whose kind disagrees with the busbar it hangs from.
An auxiliary load's parent becomes *a* busbar rather than *the* busbar.

Engine inputs become branch-shaped. Plant-level concerns — point of connection, HV, tier
voltages, rules — stay flat; kind, busbar identity, station identities, circuits, segment
data, auxiliary totals, maximum loading and the branch's own active and reactive targets move
into a per-branch structure. The previous flat accessors remain as first-branch properties so
the result-mapping layer migrates incrementally.

The power factor target stays a **single requirement at the point of connection** on combined
flow. The reactive duty is split between branches by an explicit share, defaulting to
pro-rata by active power and validated into the closed unit interval.

**Solve order**, which is the substantive change: build the shared export chain and size it
on combined power against the point-of-connection power factor target, giving the combined
active and reactive requirement at the shared MV bus; split that by branch — active pro-rata
to each branch's target, reactive by the configured share; then per branch build its
collection chain, size it with the reactive-in entry point from ticket 01, arrange it against
its own maximum loading, and size its circuits; finally size the shared HV transformer and
export once.

**This is the riskiest work in the whole feature.** Each branch's correction scalar changes
the combined flow, which changes the shared HV loss, which changes both branches'
requirements. It is also the one code path with no observable intermediate on the canvas, so
an error here is invisible until the final numbers are wrong. The outer fixed point must be
bounded by an explicit iteration cap that surfaces a non-convergence issue rather than
returning a plausible-looking number — consistent with the existing house rule that the
engine reports problems as issues the editor can display, never as silent garbage.

## Carried over from the ticket 01/02 review

Two findings were deferred to this ticket rather than fixed early, because both need the
branch reshape to land properly:

- `StationPlan.kind` and `StationResult.kind` exist but are never populated — every
  construction site takes the `"pv"` default, so a BESS station's result currently reports
  `kind="pv"`. Fleet kind cannot reach them until engine inputs become branch-shaped, which
  is this ticket. **Wire them here**; until then the fields are dead.
- `size_generation_pq` reports an *effective* power factor in a field named `pf_target`.
  Harmless while nothing calls it, but this ticket is the first caller, and it will be
  passing an assigned reactive duty for which no target exists. Decide then whether the
  field is renamed or left with a documented meaning.

**Blocked by:** 02 (BESS catalogues and station kind), 04 (Branch restructure)

**Status:** ready-for-agent

- [ ] A design may hold one busbar per fleet kind; a second busbar of a kind that already
      exists is rejected with a validation issue identifying it
- [ ] A station whose kind disagrees with its busbar's kind is rejected with a validation
      issue identifying the station
- [ ] An auxiliary load may hang from any busbar
- [ ] The point of connection carries a power target per fleet and a reactive share; a share
      outside the closed unit interval is rejected
- [ ] The reactive share defaults to pro-rata by active power when not specified
- [ ] A hybrid design solves with both fleets sized independently against their own maximum
      loading, and a shared HV transformer sized on combined power
- [ ] **Golden test: a hybrid design with zero BESS power reproduces the PV-only result to
      within 1e-9**
- [ ] A design whose refinement does not converge within the iteration cap returns a
      non-convergence issue rather than a result
- [ ] Existing single-fleet designs continue to produce identical numbers
- [ ] Python suite, frontend typecheck, tests and lint all pass

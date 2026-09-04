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
- **The refined inverter requirement is still plant-wide.** `size_plant` takes one
  `stage1` and emits one `p_inv_refined = stage1.p_inv_kw * correction`. Ticket 04
  made the *cascade* per-branch but left the refined requirement singular, so nothing
  yet expresses two fleets' refined inverter/PCS requirements separately. This ticket
  must make it per-branch — a hybrid result needs a refined figure per fleet, not one
  number covering both. Surfaced by the ticket 04 spec review.
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

## Decisions settled before implementation (2026-09-04)

**Each fleet complies with the point of connection independently.** Each branch has
its own busbar; the shared HV transformer and HV line losses are applied on top of the
combined flow and attributed back to each branch pro-rata by its busbar contribution.
So the refinement fixed point carries a genuine per-branch correction scalar, each
driven by that branch's OWN point-of-connection active target:

    delivered_i = p_busbar_i - shared_export_loss * (p_busbar_i / p_busbar_total)
    k_i *= target_i / delivered_i

The alternative — one shared scalar driven by the combined target — was rejected: with
two branches of different loss profiles the total lands on target while the lossier
fleet quietly under-delivers its own figure, which is not what the engineer drew.
`_delivered_with_frozen_cables` therefore returns per-branch delivered figures as well
as the combined total.

**Non-convergence raises.** `size_plant` raises `ValueError` naming the iteration cap;
`solve_diagram`'s existing `except ValueError` maps it to an `engine_error` issue with
`results: None`. No new issue code and no new plumbing — the editor already displays
this shape.

**`size_generation_pq.pf_target`** keeps its name with a documented meaning (the
*effective* power factor implied by the assigned P and Q at the head, not a target the
caller asked for). It is already documented that way in the function; ticket 05 is the
first caller and passes an assigned reactive duty, for which no target exists.

## Payload conventions fixed for this ticket

**Point of connection node props.** `p_target_mw` keeps its name and becomes the **PV**
target (spec: "the existing single power target remains as the PV figure for legacy
designs"). Added: `p_target_bess_mw` (default 0) and `q_share_pv`, the PV share of the
point-of-connection reactive duty, validated into the closed interval [0, 1]; the BESS
branch takes `1 - q_share_pv`. When `q_share_pv` is absent the split defaults to pro-rata
by active power.

**Busbar node props.** `fleet_kind` ("pv" | "bess", default "pv"), reusing the existing
`_fleet_kind` helper already used for stations.

**Validation codes.** `no_busbar` unchanged. `multiple_busbar` is replaced by
`duplicate_busbar` (a second busbar of a kind that already exists; `node_id` is the extra
one, the kind named in the message) and `busbar_kind_mismatch` (a station whose
`fleet_kind` disagrees with its busbar's; `node_id` is the station). `bad_q_share` for a
share outside [0, 1]. One code per rule with the kind in the message, matching how
`bad_fleet_kind` is already done.

**A drawn busbar whose fleet target is zero contributes no branch.** It is not an error:
the design solves as single-fleet. This is what makes the zero-BESS comparison meaningful
rather than a structural no-op, and it is gate 2 below.

## The zero-BESS gate, in its two real halves

The single criterion "a hybrid design with zero BESS power reproduces the PV-only result
to within 1e-9" is vacuous if read literally — a zero-target branch cannot be sized at
all, so the design collapses to single-fleet and the comparison passes for free. It is
therefore split into the two independent failures it was actually written to catch:

1. **Physics gate — golden snapshot diff.** The 8 designs in
   `.scratch/bess-module/golden_snapshot.py`, run through the new branch-shaped solve
   order, must reproduce the pre-refactor snapshot byte-for-byte. This is what catches a
   wrong export-chain / collection-chain split, which is the real risk: composing the
   backward cascade in two hops is only identical to one hop if the split is right, and
   a wrong split converges to numbers that look entirely reasonable.
2. **Topology gate — drawn BESS at zero.** A hybrid diagram carrying a real BESS busbar
   with real BESS stations drawn, but `p_target_bess_mw = 0`, must equal `solve_diagram`
   of the PV-only diagram exactly. This catches degenerate-branch handling in the graph
   layer, which the snapshot cannot see.

Neither subsumes the other.

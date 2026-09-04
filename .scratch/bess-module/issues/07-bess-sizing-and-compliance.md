# 07: BESS sizing and compliance

**What to build:** A BESS design tells the engineer how many containers it needs, how much
energy it delivers, and whether it passes.

Container count per station is read from the selected solution's duration table. It is never
interpolated, derived or rounded — the supplier's own figure is the one that appears in a
design review. Delivered energy is container count times container energy, summed across the
fleet.

Compliance gains a **second hard gate** beside the existing loading check: delivered energy
must be at least the branch's point-of-connection power times the discharge duration. Both
gates are hard, and results report per-fleet loading and the energy outcome separately, so an
engineer can see which one failed and by how much.

Discharge duration is a design-level setting **restricted to the durations the selected
solution tabulates**. It is rendered as a select, so the invalid state cannot be expressed in
the interface, *and* validated server-side, so a hand-edited payload is rejected rather than
silently accepted. No rounding or interpolation rule is needed anywhere because the invalid
state is unreachable by construction.

Auxiliary load: each BESS solution's worst-case active and reactive figures are summed across
its fleet's stations and attached as that branch's lumped busbar auxiliary load, reusing the
existing auxiliary load component and node kind. No new component and no new node kind. It
enters the cascade below the export step only and must **never** appear in PCS apparent
power — a battery station's PCS is sized for export duty alone.

**Blocked by:** 02 (BESS catalogues and station kind), 05 (Hybrid topology — engine and graph
layer)

**Status:** done (67686f2)

- [x] Container count per station comes from the selected solution's duration table, for
      every duration that table contains
- [x] Delivered energy is reported for a BESS fleet
- [x] A design whose delivered energy falls short of power times duration fails compliance
      while loading passes; the converse also holds
- [x] Loading compliance is reported per fleet, against that fleet's own maximum
- [x] Discharge duration is offered as a select limited to the solution's supported durations
- [x] A payload naming an unsupported duration is rejected server-side with a validation issue
- [x] BESS auxiliary load appears at the busbar, and is absent from PCS apparent power
- [x] Python suite, frontend typecheck, tests and lint all pass

## Amendment: BESS auxiliaries stay out of the cascade entirely (2026-09-04)

The ticket said the auxiliary draw "enters the cascade below the export step only and
must **never** appear in PCS apparent power". Those two clauses turned out to conflict,
and the review caught it.

Keeping the draw out of the Stage-1 chain leaves the *nameplate* figure `s_inv_kva`
clean — but the refinement drives each branch's delivered power up to its own
point-of-connection target, so an auxiliary load subtracted at the busbar is compensated
straight back into `s_inv_refined_kva`. The PCS was being upsized to carry it by the back
door, and the figure that stayed clean was the one that cannot move by construction.

Settled by the owner: **both figures must be clean.** A battery station's PCS is sized
for export duty alone, and the container auxiliaries are fed from a separate supply
rather than from the batteries. The draw therefore does not enter the sizing cascade at
all; it is summed per fleet and reported (`bess_aux_p_kw` / `bess_aux_q_kvar` on the
branch summary, and on the results panel) because the site still has to supply it.

The first version of the guarding test asserted only `s_inv_kva` and passed while the
requirement was broken. It now asserts `s_inv_refined_kva`, the correction factor and the
delivered figures — the ones that can actually move.

## Other review findings acted on

- Container count and delivered energy reached no user: both are now on the results panel
  alongside the container auxiliaries, and `StationNodeResult.containers` is typed.
- `_rule_opt` split out so the per-fleet lookups stop re-deriving the settings dict.
- One double flattening of `station_ids` removed; the settings panel's new block now
  matches the file's own conditional-render pattern rather than wrapping an IIFE.

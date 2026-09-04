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

**Status:** ready-for-agent

- [ ] Container count per station comes from the selected solution's duration table, for
      every duration that table contains
- [ ] Delivered energy is reported for a BESS fleet
- [ ] A design whose delivered energy falls short of power times duration fails compliance
      while loading passes; the converse also holds
- [ ] Loading compliance is reported per fleet, against that fleet's own maximum
- [ ] Discharge duration is offered as a select limited to the solution's supported durations
- [ ] A payload naming an unsupported duration is rejected server-side with a validation issue
- [ ] BESS auxiliary load appears at the busbar, and is absent from PCS apparent power
- [ ] Python suite, frontend typecheck, tests and lint all pass

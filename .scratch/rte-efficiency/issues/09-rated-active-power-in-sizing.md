# Should sizing use rated active power?

**Type:** grilling
**Status:** resolved
**Blocked by:** None

## Question

Sungrow's system curve gives the ST6900UX-4H a rated active power Pn of 1724 kW against
1800 kVA apparent. ADR-0008 lets one PCS figure (the kVA) serve as both the active limit in kW
and the apparent limit in kVA. The efficiency run now uses Pn
([How do cell efficiency, conversion efficiency and the loss chain combine into one RTE?](08-energy-accounting.md)).
Should sizing check active power against Pn too? That would change seeded fleets and PCS
loading checks (about 4 % less active power per container), so it needs its own decision and
probably an amendment to ADR-0008. Not on the efficiency run's path to its spec.

## Answer

Resolved by grilling, 2026-10-23. Recorded as an amendment to
[ADR-0008](../../../docs/adr/0008-pcs-governs-bess-conversion-and-containers-are-sized.md).

1. **Two PCS limits.** Sizing checks active power against containers × Pn and apparent power
   against containers × PCS units × PCS kVA, independently, as before at 100 % of installed
   PCS. For a 4-container ST6900UX-4H station: 6896 kW active, 7200 kVA apparent.
2. **The seed uses the same two limits.** Its station-count terms for active power divide by
   Pn per station; its apparent-power terms keep the kVA figure, so the wizard proposes fleets
   that pass their own check. Container count stays sized on energy; allocation between
   stations stays proportional to installed PCS (unchanged by the change of limit, since kW per
   kVA is fixed within a solution).
3. **Missing Pn is an error, everywhere.** A BESS solution without a rated active power cannot
   be sized, seeded or put through an efficiency run; there is no fallback to the kVA figure.
   The ST6680UX-2H has none yet, so designs using it stop solving until Sungrow supplies it
   (added to the ask list in
   [Get Sungrow's reference efficiency figures for ST6900UX-4H](07-reference-rte-figure.md)).
4. **Results.** A BESS station's `pcs_capacity_kw` becomes containers × Pn; a new
   `pcs_capacity_kva` carries the apparent limit, and `pcs_apparent_loading` is measured
   against it. The frontend does not read these fields.
5. **Order of work.** The sizing change is built on its own branch straight after this ticket,
   before the efficiency run's time-series grilling, `spec.md` and implementation.

Acceptance for the sizing change: Pn is a simulated parameter on the BESS solution (1724 kW
for the ST6900UX-4H, with provenance); the PCS active check and the seed's active terms use it;
a solution without it raises a clear error at solve and seed time; existing tests and the golden
baseline are updated for the new limits, with each changed number explained.

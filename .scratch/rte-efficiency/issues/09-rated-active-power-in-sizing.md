# Should sizing use rated active power?

**Type:** grilling
**Status:** open
**Blocked by:** None

## Question

Sungrow's system curve gives the ST6900UX-4H a rated active power Pn of 1724 kW against
1800 kVA apparent. ADR-0008 lets one PCS figure (the kVA) serve as both the active limit in kW
and the apparent limit in kVA. The efficiency run now uses Pn
([How do cell efficiency, conversion efficiency and the loss chain combine into one RTE?](08-energy-accounting.md)).
Should sizing check active power against Pn too? That would change seeded fleets and PCS
loading checks (about 4 % less active power per container), so it needs its own decision and
probably an amendment to ADR-0008. Not on the efficiency run's path to its spec.

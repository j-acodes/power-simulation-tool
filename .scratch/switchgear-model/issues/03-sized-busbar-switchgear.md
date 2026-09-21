# 03: Sized busbar switchgear

**What to build:** every busbar carries **busbar switchgear**, sized by the tool. Each **feeder**
is sized against its circuit's head current; the busbar and the **export switchgear** against
the busbar total including auxiliary load; all at the design point, with no utilization margin.
Sizing picks the smallest standard rating ≥ the current from 630, 800, 1250, 1600, 2000, 2500,
3150, 4000 A. A current above 4000 A has no admissible size: the design still solves and the
busbar is flagged. The busbar inspector shows each sized rating beside its current; the PDF
report carries the same. Only MV-side equipment is modelled. See CONTEXT.md "Busbar switchgear",
"Feeder", "Export switchgear" and ADR-0007.

**Blocked by:** 01, 02 (kept sequential by owner decision; touches neighbouring code).

**Status:** ready-for-agent

- [ ] A solved design reports, per busbar, a sized rating for the busbar, the export switchgear and each feeder, each the smallest ladder rating ≥ its current (tests at boundaries: exactly 630 A, 631 A, 4000 A)
- [ ] Auxiliary load is included in the busbar and export switchgear current, not in any feeder's
- [ ] A busbar total above 4000 A solves and raises an issue pointing at the busbar node
- [ ] Busbar inspector shows each rating and its current, marked as sized (Vitest)
- [ ] PDF report lists the sized busbar switchgear
- [ ] Full README checks pass

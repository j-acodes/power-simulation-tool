# 03: The interface shows only what the technology permits

**What to build:** An engineer working on a PV design is never shown a control belonging to a
battery fleet, and vice versa. Opening a PV design, there is no BESS busbar or BESS station
catalogue in the palette, no "BESS target (MW)" on the point of connection, no "Max loading —
BESS" override, and no discharge-duration section. A BESS design hides the PV equivalents. A
hybrid design shows both.

Shown only when the technology permits the fleet kind:

| Element | Where | pv | bess | hybrid |
|---|---|---|---|---|
| PV busbar, PV station catalogue | Palette | yes | no | yes |
| BESS busbar, BESS station catalogue | Palette | no | yes | yes |
| PV target | Inspector, point of connection | yes | no | yes |
| BESS target | Inspector, point of connection | no | yes | yes |
| PV maximum loading override | Settings | yes | no | yes |
| BESS maximum loading override | Settings | no | yes | yes |
| Discharge duration section | Settings | no | yes | yes |

The discharge-duration section already hides itself until a BESS station is drawn, so on a
BESS design this changes nothing; the effect is on a PV design, where it can now never appear.

**Also hide the seeding wizard on a BESS design.** The wizard seeds a PV cascade from a
point-of-connection target, so on a battery design it is the one remaining action that would
draw a fleet the technology forbids — a hole in palette-only enforcement. A hybrid design
keeps it: the PV half of a hybrid design is a legitimate thing to seed. Seeding a battery
fleet is out of scope for this feature and stays that way.

Everything else is technology-neutral and unchanged in all three: tier voltages, maximum
utilization, loss budgets, maximum circuit current, plant-wide maximum loading, auxiliary
loads, the HV transformer, and the entire results surface. Do not gate the results panels —
a design shows results for the fleets it actually contains, which already works.

Enforcement is by omission only. Do not add save-time or solve-time validation; ADR-0002
records why that was considered and rejected, and a rejection the engineer can reach is worse
than the drift it prevents.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The palette offers busbars and station catalogues only for fleet kinds the technology
      permits
- [ ] The point-of-connection inspector shows only the permitted fleets' targets
- [ ] The settings panel shows only the permitted fleets' maximum loading overrides
- [ ] The discharge-duration section is unreachable on a PV design
- [ ] The seeding wizard is unavailable on a BESS design and available on PV and hybrid
- [ ] Technology-neutral controls and the results surface are unchanged in all three
      technologies
- [ ] No validation is added at save or solve time
- [ ] Frontend typecheck, tests and lint pass

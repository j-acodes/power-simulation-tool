# 03: Seed a hybrid plant

**What to build:** On a hybrid design the seed wizard shows a PV section and a BESS section. Each
fleet has its own point-of-connection power, maximum loading, trunk length and spacing; export
length, interconnection, voltages, power-factor target, auxiliary load and feeders per busbar are
shared. The seed sizes each fleet as its own cascade (PV as today, BESS as ticket 02) behind the
one shared HV transformer or point of connection, iterating a fleet's count if the real
multi-branch solve shows it undersized. The substation auxiliary load goes on the first PV busbar.
Layout: point of connection and HV transformer centred, PV busbars and circuits left, BESS right.

**Blocked by:** 02: Seed a BESS plant.

**Status:** ready-for-agent

- [ ] Seeded hybrid carries both fleet power figures on the point of connection and per-kind maximum-loading rules
- [ ] Seeded hybrid validates and solves with both fleets within their loading limits and energy met
- [ ] Both HV and MV interconnection variants seed and solve
- [ ] Auxiliary load hangs off the first PV busbar
- [ ] PV nodes sit left of BESS nodes; point of connection is centred over both
- [ ] Wizard on a hybrid design shows both sections with per-fleet lengths and loading
- [ ] PV-only and BESS-only seeding unchanged
- [ ] Focused seed tests, wizard test and type checks pass

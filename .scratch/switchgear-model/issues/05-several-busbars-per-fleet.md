# 05: Several busbars per fleet on a drawn diagram

**What to build:** a drawn diagram may hold more than one busbar of the same fleet kind, in
parallel. Each busbar has its own circuits, export cable and busbar switchgear, exporting into
the one shared HV transformer, or into the point of connection for an MV interconnection. The
validator drops `duplicate_busbar` and keeps `busbar_kind_mismatch`. Loading and the pro-rata
reactive split stay **per fleet**, not per busbar; auxiliary load attaches to the busbar its node
or its stations are drawn against. Stations are never moved between busbars. The palette lets
the engineer place a second busbar of a kind already present. This supersedes ADR-0001's
one-busbar-per-fleet rule and nothing else in it: the multi-branch loss refinement it calls the
riskiest code must keep converging and keep its iteration cap.

**Blocked by:** 04.

**Status:** ready-for-agent

- [ ] A PV design with two PV busbars solves; each busbar reports its own circuits, export cable and switchgear
- [ ] Every station in a fleet runs at the same loading however many busbars the fleet has
- [ ] Splitting one busbar's circuits across two busbars leaves the fleet's POC compliance intact and changes only the export-side figures
- [ ] ADR-0001 golden still holds: a hybrid design with zero BESS power reproduces the PV-only result to within 1e-9
- [ ] A station drawn against a busbar of the wrong kind is still rejected
- [ ] Palette and validator accept a second busbar of the same kind (Vitest)
- [ ] Existing single-busbar designs: golden baseline byte-identical
- [ ] Full README checks pass; report states whether a DB reset is needed

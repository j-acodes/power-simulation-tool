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

**Status:** done

- [x] A PV design with two PV busbars solves; each busbar reports its own circuits, export cable and switchgear
- [x] Every station in a fleet runs at the same loading however many busbars the fleet has
- [x] Splitting one busbar's circuits across two busbars leaves the fleet's POC compliance intact and changes only the export-side figures
- [x] ADR-0001 golden still holds: a hybrid design with zero BESS power reproduces the PV-only result to within 1e-9
- [x] A station drawn against a busbar of the wrong kind is still rejected
- [x] Palette and validator accept a second busbar of the same kind (Vitest)
- [x] Existing single-busbar designs: golden baseline byte-identical
- [x] Full README checks pass; report states whether a DB reset is needed

## Comments

Shipped. The engine branch stays one fleet; a fleet holds several busbar sections, so the
refinement loop and its cap are unchanged and loading stays uniform per fleet. Golden baseline:
every value identical; the branch summary's pin keys moved into a per-busbar `busbars` list (not
byte-identical, by coordinator decision). No DB reset needed: the validator only got more
permissive. Found on the way: the MV-interconnection "shared export" rule counted branches, not
busbars (fixed); hybrid→single narrowing removed only the first departing busbar (fixed).
Aux on one busbar still moves the other busbar's current slightly, through the fleet's shared
correction; that is correct, so the test checks aux attachment instead.

# How does the network solve come into the engine?

**Type:** grilling
**Status:** resolved
**Blocked by:** 01

## Question

Electrisim is a reference only (map Notes), so the network solve is this tool's own code on
pandapower. Decide how that dependency enters `powertool/` while keeping its boundary (no
web/UI dependency) and its tests:

- where the network check lives (a new `powertool/` module beside the sizing engine) and
  what it takes in and returns (the sized `PlantArchitecture`, not diagram JSON);
- which libraries it adds (pandapower; whether numba and lightsim2grid are worth their
  weight in the Docker image at this plant size) and the version pin;
- test strategy: how a network check gets a golden baseline, and how a result is
  cross-checked against Electrisim on the same plant (observed in the run-locally task).

Weigh observed behaviour from the run-locally task and the Electrisim defects in the map's
Notes. Resolution is an ADR.

## Answer

Decided with the user on 2026-10-22 and recorded as
[ADR-0010](../../../docs/adr/0010-network-check-is-own-code-on-pinned-pandapower.md).

- **Where:** a new `powertool/network/` package. It holds a net builder plus one module per
  check. No sizing module imports it.
- **In:** the sized `PlantArchitecture` plus a grid equivalent at the POC (Sk", X/R). No diagram
  JSON and no catalogue reads. The sized design already carries cable selections, station
  transformers (through each branch's layout) and the HV transformer. The grid equivalent's
  source belongs to "Where do short-circuit inputs come from?".
- **Out:** this tool's own result objects (value, limit, pass/warn/fail per check). pandapower
  tables never leave the package. How results surface stays fog on the map.
- **Libraries:** pandapower only, a normal dependency pinned `==3.3.2` (Electrisim's version) in
  `requirements.txt` and the Dockerfile. The image grows by about 150–200 MB. No numba or
  lightsim2grid until a P-Q sweep takes more than about 10 s.
- **Tests:** a separate network baseline over the existing fixture designs, compared within a
  tolerance. Fixed cross-check cases rebuild the Electrisim sample plant and assert against
  Electrisim's saved load-flow and PV fault-contribution figures (with provenance), plus hand
  calculations. They exclude its known defects. Electrisim is never run by tests.

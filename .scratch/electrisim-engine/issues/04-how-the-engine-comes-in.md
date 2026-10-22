# How does the network solve come into the engine?

**Type:** grilling
**Status:** open
**Blocked by:** 01, 02

## Question

Choose how load flow and short-circuit reach `powertool/` while keeping its boundary (no
web/UI dependency) and its tests:

- (a) depend on pandapower directly, writing this tool's own diagram-to-network builder and
  checks, with Electrisim as a worked reference only;
- (b) as (a), but vendor Electrisim's standalone modules (`storage_q_capability`,
  `converter_sc_electrisim`, a de-coupled grid-code P-Q sweep);
- (c) run Electrisim's backend as a separate service and call it.

Weigh licence (02), observed behaviour (01), the Electrisim defects listed in the map's
Notes, dependency weight (pandapower, numba, lightsim2grid in the Docker image), and test
strategy (how a network check gets a golden baseline). Resolution is an ADR.

# How does the network solve come into the engine?

**Type:** grilling
**Status:** open
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

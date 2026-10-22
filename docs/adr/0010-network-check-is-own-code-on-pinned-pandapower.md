# The network check is this tool's own code on pinned pandapower, beside the sizing engine

The **network check** (load flow, IEC 60909 short-circuit, grid-code P-Q/U-Q, BESS operating
cases) lives in a new `powertool/network/` package. One part builds a pandapower net from the
sized design, and each check is its own module. Its input is the sized `PlantArchitecture` (which
already carries cable selections and lengths, station transformers through each branch's layout,
and the HV transformer) plus a **grid equivalent** at the POC (short-circuit power and X/R). It
never takes diagram JSON or reads the catalogue. It returns this tool's own result objects: per
check, the value, the limit, and pass / warn / fail. pandapower tables never cross the package
boundary, so the API, PDF and frontend do not depend on pandapower. The backend calls the check
after sizing. No sizing module imports `powertool/network/`, so the sizing path is unchanged.

pandapower is a normal dependency, pinned exactly at `pandapower==3.3.2`, the version Electrisim
runs. It goes in both `requirements.txt` and the Dockerfile. numba and lightsim2grid are not
installed. Raising the pin is a deliberate change that regenerates the network baseline.

Tests have two layers. A **network baseline**, separate from the sizing golden snapshot, runs
the existing fixture designs and compares within a tolerance (load flow is iterative). Fixed
**cross-check cases** rebuild the Electrisim sample plant ("Run Electrisim end-to-end locally")
and assert this tool's results against Electrisim's saved figures, with provenance noted. These
cases cover only results Electrisim gets right: load flow and PV fault contribution. Hand
calculations are added alongside, such as Ik" at the POC from the grid's short-circuit power.
Electrisim is never run by the tests.

## Considered Options

- **Copy or call Electrisim's backend.** Rejected: Electrisim is a reference only (licence
  unconfirmed, frontend-coupled modules, defects listed in the map's Notes).
- **Take diagram JSON as input.** Rejected: it would duplicate the backend's diagram-to-engine
  mapping and check a different model from the one that was sized.
- **pandapower as an optional extra.** Rejected: the image saving (~150–200 MB of
  numpy/scipy/pandas) does not justify a second, check-less path to test.
- **Add numba / lightsim2grid now.** Deferred: plants have tens of buses. Revisit if a P-Q sweep
  takes more than about 10 s.
- **Version range instead of an exact pin.** Rejected: a library drift would blur cross-checks
  against Electrisim and move baselines silently.
- **Extend the sizing golden snapshot.** Rejected: a pandapower bump would mix solver drift into
  sizing diffs.

## Consequences

The runtime image grows by roughly 150–200 MB. The grid equivalent is a new input that this tool
does not hold yet; its source is decided under "Where do short-circuit inputs come from?".
Electrisim figures frozen into tests are data, not code, and carry their source.

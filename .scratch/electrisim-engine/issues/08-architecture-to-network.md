# How does a sized design become a pandapower net?

**Type:** grilling
**Status:** claimed
**Blocked by:** None

## Question

ADR-0010 has the network check build a pandapower net from the sized `PlantArchitecture`.
Decide the mapping:

- which buses exist (POC/HV, MV busbar per busbar section, one MV bus per station, station LV
  bus) and how stations, circuits, segments, export cable and HV transformer become lines and
  transformers, including parallel cables and parallel HV transformers;
- whether identical stations or circuits are aggregated or every station is modelled;
- how PV and BESS stations enter as generation (sgen vs storage; BESS charging direction,
  where pandapower storage +P means charging), and how auxiliary loads enter;
- what the base operating point is (the Stage-1 delivered P/Q, or something else).

The grid equivalent at the POC is out of this ticket ("Where do short-circuit inputs come
from?"); treat it as given.

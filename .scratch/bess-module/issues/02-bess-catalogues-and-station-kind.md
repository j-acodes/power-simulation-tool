# 02: BESS catalogues and station kind

**What to build:** An engineer can place a station on the canvas, mark it as a BESS station,
choose a supplier solution from a new catalogue, and have that design validate and solve.

A station gains a **fleet kind** with values `pv` and `bess`. A station that does not declare
one parses as `pv` — this is the backward-compatibility guarantee for every design already
saved, and it must be tested explicitly.

Two new catalogues load alongside the existing transformer and cable catalogues: a **BESS
solution** catalogue, and a **separate BESS station-transformer** catalogue (deliberately not
a category field on the existing transformer catalogue). Both are exposed by the catalogue
endpoint and mirrored in the frontend types. The palette offers only the transformers valid
for the kind of station being placed.

The BESS solution shape encodes several settled decisions at once:

```python
@dataclass(frozen=True)
class BessSolution:
    name: str
    e_container_kwh: float
    pcs_p_kw: float
    pcs_lv_kv: float
    aux_p_kw: float                          # worst case, from the spec sheet
    aux_q_kvar: float
    containers_by_duration: dict[float, int] # discharge hours -> containers per station
```

Sizing behaviour does not change in this ticket. A BESS station sizes exactly as a PV station
does, which is already correct — a discharging battery is modelled as a generator. Container
counts, delivered energy and the energy compliance gate arrive in ticket 07.

Station LV voltage becomes the station transformer's own rating rather than the diagram-level
default. This is smaller than it appears: the transformer loss model is expressed in per-unit
of rating and ignores voltage, and no LV cable is ever sized, so LV is a catalogue,
validation and labelling concern rather than a cascade-physics one. The diagram-level LV
setting survives as the default for custom transformers.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A station declares a fleet kind of `pv` or `bess`; a station declaring none parses as
      `pv` and solves identically to before
- [ ] A BESS solution catalogue and a separate BESS station-transformer catalogue load at
      startup through the existing component database
- [ ] The catalogue endpoint returns both new collections, and the frontend types mirror them
- [ ] The palette offers PV station transformers for PV stations and BESS station
      transformers for BESS stations, and never mixes them
- [ ] A BESS station that names no solution is rejected with a validation issue identifying
      the offending station
- [ ] A BESS station whose transformer LV rating disagrees with its solution's PCS voltage is
      rejected with a validation issue
- [ ] A single-fleet BESS design validates and solves end to end, producing the same numbers
      an equivalent PV design would
- [ ] Python suite, frontend typecheck, tests and lint all pass

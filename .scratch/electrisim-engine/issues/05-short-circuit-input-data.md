# Where do short-circuit inputs come from?

**Type:** grilling
**Status:** resolved
**Blocked by:** None

## Question

IEC 60909 and the POI fault study need inputs the catalogues lack: inverter and PCS fault
current contribution (Ik" or k factor, per fault type), transformer vector group and
zero-sequence impedance (and neutral earthing), numeric switchgear short-time withstand
and peak ratings (today a text string such as "IAC AFL 20 kA / 1 s"), and the grid's
short-circuit power and X/R at the POC (Sk max/min).

For each: is it a simulated catalogue parameter transcribed from datasheets, a project
input typed per design, or a default (e.g. IEC 60909 k = 1.1–1.2 for converters) flagged
as a project assumption like the existing ones? Which are blocking for a first check and
which can start as defaults?

## Answer

Decided with the user on 2026-10-22.

**Scope of the first check:** three-phase faults only (IEC 60909 Ik", ip, Ib at the POC, the MV
busbars and the stations). Single-phase-to-earth faults wait until the zero-sequence data
below exists.

| Input | Source | Default | Blocks the first check? |
|---|---|---|---|
| Grid Sk" max/min and X/R at the POC | Project input, typed per design from the grid-connection offer | None | **Yes.** Without it the short-circuit check does not run and the design carries a warning saying so. No placeholder. |
| Inverter / PCS fault contribution (k factor or Ik") | Catalogue parameter, transcribed from datasheets | k = 1.2, declared as a project assumption when the datasheet is silent (the ADR-0006 stance: default in the safe direction, declare it) | No |
| Transformer vector group, zero-sequence impedance | Catalogue parameter | Dyn11 for station transformers, YNd for the HV transformer | No (single-phase only) |
| Neutral earthing | Project input (the site's earthing system) | Not needed yet | No (single-phase only) |
| Switchgear short-time withstand Ik/tk and peak Ip | Catalogue parameter, numeric, transcribed from datasheets | Ip = 2.5 × Ik at 50 Hz when only Ik is published | No for fault levels; yes for a breaker-duty verdict on that switchgear |
| POC circuit breaker rating | Project input | None | No for fault levels; yes for a POC breaker-duty verdict |

BESS PCS units contribute fault current like PV inverters. Electrisim's zero storage
contribution is a defect, not a reference.

**Findings:**

- `rmu_short_time_withstand` on the PV stations in `data/transformers.yaml` holds internal-arc
  classification strings ("IAC AFL 20 kA / 1 s", "IAC A 20 kA / 1 s"). The Huawei block has
  the same string in `internal_arc_classification` too. IAC is the internal-arc rating, not
  the short-time withstand current. The numeric withstand must be re-read from the
  datasheets, not parsed from these strings. The BESS stations' strings ("20 kA / 3 s or
  25 kA / 1 s") are genuine withstand figures.
- No catalogue holds a POC or HV circuit breaker; its rating is a per-design input.

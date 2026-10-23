# Should the efficiency run's discharge be capped at the POC capacity?

**Type:** grilling
**Status:** resolved
**Blocked by:** None

## Question

The efficiency run discharges at full rated active power (N × Pn × derating) and charges at the
POC capacity. Because installed PCS always exceeds the POC capacity, discharge exports more
than the connection allows: 108 MW through a 100 MW POC in the spec's worked example. Cap it, or
keep it as a reference-cycle simplification?

## Answer

Resolved by the owner, 2026-10-23, while splitting [the spec](../spec.md) into tickets.

**Cap it.** Discharge export at the POC never exceeds the POC capacity. When N × Pn × derating
would export more, the AC power at the container terminals is reduced until export equals the
POC capacity, and the leg stretches (the energy cycled is unchanged). The reference cycle stays
physically possible. In the worked example the 25 °C discharge runs at 101,942 kW AC for
4.27 h, exporting exactly 100 MW; RTE stays 88.6 %. The 48 °C case is below the cap already.

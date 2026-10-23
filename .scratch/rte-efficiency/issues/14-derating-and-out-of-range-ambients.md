# 14: Hot-ambient PCS derating and out-of-range ambients

**What to build:** The run honours the PCS derating curve and reports it. At a hot ambient
the containers run at Pn × derating on both legs; the energy cycled is unchanged, so the cycle
stretches; the charge leg imports the lesser of the POC capacity and what drives the derated
PCS; load losses fall with power while no-load losses and auxiliary consumption run over the
longer cycle. `PCS power % of rated` becomes real. Ambients outside the published range clamp
to the edge with one warning (count of clamped timestamps, extremes seen). See
[spec](../spec.md) and [ticket 04](04-derated-efficiency-run.md).

Scope includes adding the ST6900UX-4H derating curve to the catalogue with provenance
(1.0 Pn to 45 °C, linear to 0.6 Pn at 50 °C). A solution without a derating curve runs at
100 % with a warning.

**Blocked by:** 12

**Status:** done

- [x] The worked example at 48 °C reproduces: PCS power 76 %, operating RTE 87.6 %, charge
      import 85,954 kW (below the POC capacity).
- [x] Derating is never a loss: exported energy stays within loss-chain differences of the
      non-derated case.
- [x] Clamping produces one warning with the count and extremes; a missing curve warns.

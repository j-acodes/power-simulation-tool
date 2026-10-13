# How do auxiliary-consumption tables and the derating curve attach to the catalogue and get looked up?

**Type:** grilling
**Status:** resolved
**Blocked by:** 05

## Question

Decide how the tables in `data/manufacturer-curves/sungrow-pt3/` become catalogue data:
container auxiliary consumption on the BESS solution (ST6900UX-4H), MVS auxiliary consumption
on the station transformer (MVS7400-LS), and the derating curve on the BESS solution. Decide
the lookup between published ambients: linear interpolation for the container points and the
derating curve, steps for the banded MVS table, and how that sits against ADR-0004's "never
interpolate" stance for AC power at ambient (likely an ADR of its own). Decide behaviour
outside the published range (−30…50 °C): clamp, refuse, or warn. Whether these are simulated
parameters (the engine reads them) is implied, but say so.


## Answer

Resolved by grilling, 2026-10-13. Recorded as
[ADR-0009](../../../docs/adr/0009-efficiency-curves-interpolated-ratings-not.md).

1. **Inline on the catalogue entry, as simulated parameters.** The engine reads them. The
   container auxiliary-consumption tables (one per cycles-per-day reference, operating and
   standby kW per container at each published ambient) and the PCS derating curve (fraction of
   rated power at each published ambient) sit on the BESS solution in `data/bess.yaml`. The
   banded MVS auxiliary-consumption table (operating and standby kW per MVS per ambient band)
   sits on the station transformer in `data/bess_transformers.yaml`. Each block carries its
   provenance (source table or figure, preliminary).
2. **Lookup, recorded in ADR-0009.** Ratings stay lookup-only (ADR-0004). Curves used only to
   model efficiency interpolate linearly between published points: the container tables
   bilinearly in ambient and cycles per day, the derating curve in ambient. Banded tables step:
   the band containing the ambient applies.
3. **Ambient outside the published range** (−30…50 °C for Sungrow PT3) clamps to the nearest
   edge, and the run warns with the number of timestamps clamped and the extremes seen; the
   same rule as cycles per day. Above 50 °C this holds the PCS at 0.6 Pn although the container
   may in reality shut down; the warning is how that surfaces.
4. **Missing curves.** No container auxiliary-consumption table: error, since it carries all
   of the run's ambient dependence. No derating curve: 100 % of rated power, with a warning. No
   MVS auxiliary-consumption table (for example the `GENERIC_*` placeholders): zero, with a
   warning; it is about 4 kW per MVS against about 50 kW of container draw.
5. **Unit counts without a design.** The caller types the BESS solution, a paired station
   transformer, the station count and the container count. A container count above stations
   times the pairing maximum is an error (ADR-0008's rule). This fills a gap left by
   [Which losses sit between the battery and the POC, from a design and without one?](03-loss-chain.md),
   whose without-design inputs named no counts. With a design, the counts come from the design.

## Comments

- 2026-10-13, from [How does cycles per day enter the efficiency run?](05-cycles-per-day.md):
  container tables are also interpolated linearly between cycles-per-day references (clamped
  outside, with a warning). The ADR-0004 decision here must cover that axis too, and the
  catalogue shape must hold one container table per published reference.

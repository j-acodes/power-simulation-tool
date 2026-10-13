# How do auxiliary-consumption tables and the derating curve attach to the catalogue and get looked up?

**Type:** grilling
**Status:** open
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

## Comments

- 2026-10-13, from [How does cycles per day enter the efficiency run?](05-cycles-per-day.md):
  container tables are also interpolated linearly between cycles-per-day references (clamped
  outside, with a warning). The ADR-0004 decision here must cover that axis too, and the
  catalogue shape must hold one container table per published reference.

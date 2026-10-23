# How does cycles per day enter the efficiency run?

**Type:** grilling
**Status:** resolved
**Blocked by:** None

## Question

Sungrow publishes auxiliary consumption for PowerTitan 3.0 at a reference of 1 and of
2 cycles/day, and the figures differ (notably standby at 15–45 °C). The efficiency run is
evaluated per timestamp and does not know the dispatch. Is cycles per day a fixed project
parameter that selects the table, an input per run (interpolating or stepping between 1 and
2), or is one table chosen and the other ignored? What happens for a solution that publishes
only one reference? Also settle what "operating power" and "standby power" mean: average
draw over the time spent in that state, per container.

## Answer

Resolved by grilling, 2026-10-13. In the Sungrow PT3 tables, cycles per day barely moves
operating draw but raises standby draw by up to about 50 % (25 °C: 4.10 vs 6.20 kW per
container), plausibly because cells cycled more often are still warm when they go idle.

1. **Static parameter.** Cycles per day is one value for the whole run, part of the static
   configuration, never a per-timestamp input. It selects the container auxiliary-consumption
   table only; the MVS table has no cycles dimension.
2. **Interpolate, clamp outside.** Between published references, operating and standby draw
   are interpolated linearly in cycles per day. Outside the published range the nearest
   reference's table is used. The caller does not control what cycles per day it is given, so
   refusing would block legitimate runs. Interpolating between published tables departs from
   ADR-0004; [How do auxiliary-consumption tables and the derating curve attach to the catalogue and get looked up?](06-curve-storage-and-lookup.md)
   must confront that for cycle references as well as ambients.
3. **Single reference.** A solution that publishes one reference uses that table for any
   cycles per day: the same nearest-table rule, with no special case.
4. **Warning on clamp.** Whenever the nearest table stands in for the requested value, the run
   completes and returns a warning, outside the CSV, naming the requested cycles per day and
   the reference used.
5. **Required.** Cycles per day is required whenever the solution publishes more than one
   reference; there is no default, since it moves standby draw by about 50 %.
6. **Meaning of operating and standby.** Each is the average draw per unit (per container, or
   per MVS for the MVS table) over the time spent in that state, at that ambient. Operating
   applies over the whole efficiency run, both legs; standby feeds the idle figure. Sungrow is
   asked to confirm this in
   [Get Sungrow's reference efficiency figures for ST6900UX-4H](07-reference-rte-figure.md).
7. **Output unchanged.** The CSV keeps its four columns; the cycles per day used is not echoed.

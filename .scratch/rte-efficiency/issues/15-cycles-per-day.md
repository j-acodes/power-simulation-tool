# 15: Cycles per day

**What to build:** The modeller sets cycles per day, and the container auxiliary consumption
interpolates linearly between the published references (bilinear with ambient). Outside the
published references, or for a single-reference solution, the nearest table applies with a
warning naming the requested value and the reference used. Cycles per day is required when a
solution publishes more than one reference. See [spec](../spec.md) and
[ticket 05](05-cycles-per-day.md).

Scope includes adding the ST6900UX-4H 2 cycles/day container table to the catalogue with
provenance.

**Blocked by:** 12

**Status:** done

- [x] 1.5 cycles/day at 25 °C uses the midpoint of the two tables (operating and standby).
- [x] 3 cycles/day uses the 2 cycles/day table and warns; omitting it is an error for PT3.
- [x] The output CSV is unchanged (cycles per day is not echoed).

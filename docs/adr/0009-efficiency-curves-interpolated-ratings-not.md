# Efficiency curves are interpolated between published points; ratings are not

ADR-0004 forbids computing a rating a supplier does not publish. The efficiency run needs
supplier curves of a different kind: auxiliary consumption per container against ambient and
cycles per day, auxiliary consumption per MVS against ambient bands, and PCS derating against
ambient. These are read only to model efficiency, never to size equipment. They are
interpolated linearly between published points: the container tables bilinearly in ambient and
cycles per day, the derating curve in ambient. A table the supplier publishes in bands is
stepped: the band containing the ambient applies. Outside the published range the nearest
edge applies and the run warns. Ratings used for sizing remain lookup-only under ADR-0004.

## Considered Options

- **Lookup only, as ADR-0004.** Rejected: between published ambients a step lookup would make
  round-trip efficiency jump at 15, 25 and 35 °C for no physical reason, and a weather series
  sits between published points almost all the time.
- **Step every table, including point tables.** Rejected for the same reason; banded tables are
  stepped only because the supplier publishes them as bands.
- **Refuse ambients outside the published range.** Rejected: a few hours beyond the range would
  stop a multi-year run. The warning reports how many timestamps were clamped.

## Consequences

The split follows what each figure is for. A rating is procured and sizes the plant, so an
invented rating is a sizing risk, and ADR-0004's conservative upward fallback still applies to
it. An efficiency curve estimates realistic behaviour, where a figure between two measured
points is better than either neighbour. A curve the catalogue holds must therefore say which
kind it is; the auxiliary-consumption tables and the derating curve are efficiency curves.
Clamping above the hottest published point holds the last derating figure although a real
container may shut down there; the warning is how that surfaces.

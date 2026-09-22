# 02: Labels, legend and assumed values

**What to build:** the single-busbar PV sheet from 01 carries the figures. POC voltage and MW;
HV transformer model and MVA; busbar voltage; each feeder's switchgear rated current; every
cable segment (export spans and every circuit segment) with size, material, parallel-run count
and length; each station's transformer model and kVA; each inverter as "× N model". Model names
are catalogue model keys, not display labels. Any fallback value (e.g. the 630 A switchgear
rated current) is marked † and listed with its reason in a note on the sheet, driven by the same
data as the existing fallback notices. Each sheet gets a symbol legend and the note that
protection devices are indicative. No losses, loading or DC capacity on the drawing.

**Blocked by:** 01

**Status:** done

- [x] Layout-model tests assert the label text on tagged elements: POC, HV transformer, busbar, feeders, a tapered circuit's per-segment cables, a parallel-run segment, station transformer, inverter count and model key
- [x] A design using the 630 A switchgear fallback shows † on that feeder/station and lists it in the sheet notes; a design with no fallback has no † and no fallback note
- [x] Legend and indicative-devices note present on every sheet
- [x] Browser check: downloaded SLD opened and screenshot reported
- [x] `tests/golden_baseline.json` byte-identical; full pytest, Vitest, build and lint pass

## Comments

- Feeder ratings honour pins via `busbar_switchgear_rating(i_trunk_a, pin)`; the pin lookup currently reads the first fleet's first busbar only — ticket 03 must index by fleet and busbar.
- The station-switchgear fallback † sits on the station tag, never the feeder (the feeder is sized from the ladder).

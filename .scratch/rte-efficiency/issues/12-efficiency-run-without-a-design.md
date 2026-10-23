# 12: Efficiency run without a design (tracer bullet)

**What to build:** A modeller passes a CSV of `timestamp, ambient °C` and a typed-in BESS
configuration (no design) and gets back a CSV with `timestamp, operating RTE %, idle loss %,
PCS power % of rated`, plus a list of warnings, from a pure engine function and a thin CLI. In
this ticket the operating RTE column is real; `idle loss %` and `PCS power % of rated` may be
placeholders filled by tickets 13 and 14, but the four-column shape is final.

Scope (see [spec](../spec.md), "Implementation Decisions"):

- The catalogue gains the efficiency-run simulated parameters for the ST6900UX-4H with
  provenance: the four conversion-efficiency items (product used), the cell RTE default
  (95 %, marked as a project assumption), the 1 cycle/day container auxiliary-consumption
  table (operating and standby), and on the MVS7400-LS the banded MVS auxiliary-consumption
  table. Rated active power already exists.
- The without-design configuration: solution, paired station transformer, station count,
  container count, POC capacity, load loss % and no-load loss % (both of the fleet's rated
  active power), cell RTE override. A container count above stations × pairing maximum, a POC
  capacity at or above installed rated active power, an unpaired transformer, or a solution
  without rated active power is an error.
- The efficiency run at full rated power (no derating yet): discharge capped at the POC
  capacity ([ticket 11](11-discharge-above-poc-capacity.md)), charge at the POC capacity, cell
  RTE once on the charge leg, conversion efficiency both ways, operating auxiliary consumption
  over both legs, typed load and no-load losses.
- Container tables interpolate linearly in ambient; the MVS table steps by band. A missing
  container table is an error; a missing MVS table is zero with a warning.
- The engine module has no web or UI dependency.

**Blocked by:** 11 (resolved)

**Status:** done

- [x] The spec's worked example at 25 °C reproduces: operating RTE 88.6 % (within 0.01 point
      of the hand calculation in the spec's Further Notes), discharge capped at 100,000 kW.
- [x] With the loss chain and auxiliary consumption zeroed, RTE equals cell RTE × η² at every
      ambient.
- [x] Each invalid configuration above raises a clear error; a missing MVS table warns.
- [x] The CLI reads and writes the CSVs and prints warnings separately.
- [x] Catalogue entries carry provenance; the README test commands pass.

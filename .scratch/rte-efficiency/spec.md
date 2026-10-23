# Spec: BESS efficiency run (round-trip efficiency at the point of connection)

**Status:** split into tickets 11–16 under `issues/`, 2026-10-23. Time-series edge cases are
deferred (see Further Notes).
**Decisions:** tickets 01–10 under `issues/`, summarised in [map.md](map.md).
**Decision records:** [ADR-0009](../../docs/adr/0009-efficiency-curves-interpolated-ratings-not.md)
(curve lookup), the
[ADR-0008 amendment](../../docs/adr/0008-pcs-governs-bess-conversion-and-containers-are-sized.md)
(rated active power), ADR-0004 (ratings stay lookup-only).

## Problem Statement

Downstream revenue and dispatch models need to know how much energy a BESS loses, and that loss
depends on the weather. Today they use one flat round-trip efficiency (RTE) from a datasheet,
measured at some unstated boundary, with no auxiliary consumption and no transformer or cable
losses. A hot afternoon, when the cooling works hardest and the PCS derates, looks the same as
a mild night. There is also no figure for what the plant costs to keep energised while it sits
idle.

## Solution

An engine module that takes an ambient-temperature time series and a catalogue BESS solution
and writes, per timestamp:

| Column | Meaning |
|---|---|
| `timestamp` | echoed from the input |
| `operating RTE %` | round-trip efficiency of one **efficiency run** at that ambient, measured at the point of connection (POC) |
| `idle loss %` | energy imported at the POC per hour while idle, as a % of the fleet's nominal energy |
| `PCS power % of rated` | the power available at that ambient (100 unless hot-ambient derating applies) |

Each interval of a battery's dispatch is charging, discharging or idle; the downstream model,
not this module, decides which figure applies. Derating is reported as a power cap, never
counted as a loss.

Worked result (64 ST6900UX-4H containers, 16 stations, 100 MW POC, typed-in losses, 1
cycle/day; derivation under Further Notes):

| Ambient | Operating RTE at POC | Idle loss | PCS power |
|---|---|---|---|
| 25 °C | 88.6 % | 0.094 %/h | 100 % |
| 48 °C | 87.6 % | 0.237 %/h | 76 % |

For comparison, the container alone (cells and conversion, no auxiliaries or loss chain) is
92.1 % at any ambient.

## User Stories

1. As an energy modeller, I give a CSV of `timestamp, ambient °C` and a BESS configuration and
   get the four-column CSV back, so my dispatch model can use weather-dependent efficiency.
2. As an engineer with a solved design, I point the run at that design so its own transformers,
   cables, station count and POC capacity are used.
3. As an engineer at early stage with no design, I type the solution, station transformer,
   station and container counts, POC capacity, and load and no-load loss percentages.
4. As a modeller, I set cycles per day, because it changes standby draw by up to ~50 %.
5. As a reviewer, I see warnings (outside the CSV) whenever an input was clamped or a curve was
   missing, so nothing is silently extrapolated.

## Implementation Decisions

### Interface

- A pure function in `powertool/` (no web or UI dependency) plus a CLI wrapper. API and UI
  exposure are a later effort.
- Input: rows of `timestamp, ambient °C`; everything else is static configuration. Each row is
  evaluated independently: the result for a row depends only on its ambient and the
  configuration. Timestamps are echoed verbatim.
- Output: the four columns above, plus a list of warnings returned separately.

### Configuration

| Input | With a design | Without a design |
|---|---|---|
| BESS solution | from the design (a conflicting choice is an error) | typed |
| Station transformer | from the design | typed, must be paired with the solution |
| Station count, container count | from the design | typed; containers ≤ stations × pairing maximum, else error |
| POC capacity | from the design | typed, required |
| Loss chain | the design's own elements (below) | typed load loss % and no-load loss % |
| Cycles per day | required when the solution publishes more than one reference | same |
| Cell RTE | catalogue default, overridable | same |

A design with no BESS fleet is an error. A solution without rated active power is an error
(ADR-0008 amendment).

### Catalogue data (simulated parameters on existing entries)

On the BESS solution (`data/bess.yaml`), each block with its provenance:

- `rated_active_power_kw` (Pn): already present, 1724 kW for ST6900UX-4H.
- Conversion efficiency DC terminals → MVS LV, as four stored items whose product is used:
  DC cable 99.90 %, PCS bus 99.95 %, PCS 98.70 %, LV cable 99.90 % (product 98.45 %; Sungrow
  quotes 98.4 %). Constant at every power level, both directions.
- Cell (DC) RTE: default 95 %, marked as a project assumption, not supplier data.
- Container auxiliary consumption: one table per cycles-per-day reference (1 and 2 for PT3),
  operating and standby kW per container at each published ambient (−30…50 °C).
- PCS derating curve: fraction of Pn per ambient (PT3: 1.0 to 45 °C, linear to 0.6 at 50 °C).

On the station transformer (`data/bess_transformers.yaml`):

- MVS auxiliary consumption: operating and standby kW per MVS, by ambient band
  (PT3: [−30,10), [10,35), [35,50]).

### Lookup (ADR-0009)

- Container tables: linear in ambient and in cycles per day (bilinear).
- Derating curve: linear in ambient.
- Banded MVS table: the band containing the ambient.
- Ambient outside the published range clamps to the edge, with one warning giving the number
  of timestamps clamped and the extremes seen. Cycles per day outside the published references
  uses the nearest table, with a warning.
- Missing container table: error. Missing derating curve: 100 % with a warning. Missing MVS
  table: zero with a warning.

### The efficiency run (one per timestamp)

Notation: N containers, S stations, E nominal energy per container (6904 kWh), d derating
factor, η conversion efficiency, ρ cell RTE.

1. **Discharge.** The run cycles the nominal energy N·E at the DC terminals. AC power at the
   container terminals is P_ac = N · Pn · d, unless the resulting export would exceed the POC
   capacity: then P_ac is reduced until the export equals the POC capacity
   ([ticket 11](issues/11-discharge-above-poc-capacity.md)). Export at the POC = P_ac − loss
   chain(P_ac) − no-load losses − operating auxiliary consumption. The DC side runs at
   P_ac ÷ η, so the leg lasts t_d = N·E·η ÷ P_ac (~3.94 h at full Pn).
2. **Charge.** The leg must put N·E ÷ ρ back in at the DC terminals, so the cycle closes. Import
   at the POC is the lesser of the POC capacity and the import that drives the PCS at N·Pn·d.
   Walking inward from the POC: subtract auxiliary consumption and no-load losses, then the load
   losses, to get the AC power into the containers; DC power = that × η; t_c = (N·E ÷ ρ) ÷ DC
   power.
3. **RTE = (export × t_d) ÷ (import × t_c).** Each leg is constant power; no time stepping;
   the run starts empty with no rest between legs.
4. **Auxiliary consumption** over both legs: N × container operating kW + S × MVS operating
   kW, as published (no scaling by power). It is drawn at the MV busbar, so it carries HV
   transformer and export-cable losses (whichever of the two the design has), but not
   station-transformer or collection-cable losses.
5. **Loss chain, with a design:** the existing engine losses, reused, symmetric in direction:
   station transformers (load and no-load), collection cables, HV transformer (load and
   no-load), export cable. Transformer figures are the catalogue `pk`/`p0` against the 40 °C
   rating, with no ambient dependence. In a hybrid, PV is at zero and the shared HV transformer
   and export cable count in full. Busbar, switchgear and LV cable losses are ignored; PCS
   losses are inside η.
6. **Loss chain, without a design:** load loss = typed % × fleet rated active power (N·Pn) at
   full power, scaled with the square of power below it; no-load loss = typed % × N·Pn.
   Auxiliary consumption is subtracted at the POC with no extra losses.
7. **Derating:** the same energy over a longer cycle; load losses fall with power, no-load
   losses and auxiliary consumption run over the longer time.

### The idle figure

**Idle loss = (N × container standby kW + S × MVS standby kW + no-load losses of every station
transformer and the HV transformer) ÷ (N × E) × 100, in % per hour.**

- All transformers stay energised (hot standby); in a hybrid the HV transformer counts in full.
- PCS standby draw is assumed to be inside Sungrow's standby auxiliary consumption.
- No load losses on the idle draw; no cell self-discharge; independent of derating.
- Without a design, the no-load term is the typed no-load % × N·Pn.
- It is energy imported at the POC: grid import, not a fall in state of charge.

## Testing Decisions

- Pure-function tests in the existing pytest suite, isolated per `tests/conftest.py`.
- A hand-computed anchor reproducing the worked example (both ambients) to within 0.01 point.
- The container-only identity: with the loss chain and auxiliary consumption at zero, RTE
  equals ρ·η² (92.1 %) at every ambient.
- Derating: at 48 °C, `PCS power % of rated` = 76, and exported energy equals the non-derated
  case's to within loss-chain differences (energy is fixed, not power).
- Lookup: interpolation between ambients and cycles references, band stepping, clamping with
  the warning count, each missing-curve rule.
- With a design: a seeded design yields the same station count, solution and POC capacity as
  the design, and a design without a BESS fleet is an error.
- The idle figure, with and without a design, and its independence from derating.

## Out of Scope

- Degradation and augmentation (beginning of life only).
- Dispatch or energy management.
- Non-unity power factor at the POC.
- API and UI exposure.
- Cell self-discharge.

## Further Notes

### Deferred: time-series edge cases

Resolution detection, gaps, and timezone/DST handling are not decided. Because each row is
evaluated independently, none of them changes a computed figure; they matter for input
validation only. The first implementation echoes timestamps unchanged and does not validate
spacing.

### Open questions for Sungrow

Recorded in [ticket 07](issues/07-reference-rte-figure.md): definitions of operating and
standby in Tables 7–9, whether standby includes PCS standby draw, behaviour outside −30…50 °C,
real MVS7400-LS load and no-load losses, and the ST6680UX-2H's rated active power.

### Worked example (without a design)

64 containers, 16 stations, POC 100 MW, load loss 1.0 %, no-load 0.1 % (of 110,336 kW),
1 cycle/day, ρ = 95 %, η = 98.45 %.

| | 25 °C | 48 °C |
|---|---|---|
| Derating d | 1.00 | 0.76 |
| Operating aux (64 × container + 16 × MVS) | 890 kW | 1,351 kW |
| Discharge: AC power / export (capped at POC) | 101,942 / 100,000 kW | 83,855 / 81,757 kW |
| Discharge: duration / energy exported | 4.27 h / 426.7 MWh | 5.19 h / 424.1 MWh |
| Charge: import / AC into containers | 100,000 / 98,127 kW | 85,954 / 83,855 kW |
| Charge: duration / energy imported | 4.81 h / 481.4 MWh | 5.63 h / 484.2 MWh |
| **Operating RTE at POC** | **88.6 %** | **87.6 %** |
| Idle draw (standby aux + no-load) | 417 kW | 1,048 kW |
| **Idle loss** (÷ 441.9 MWh) | **0.094 %/h** | **0.237 %/h** |

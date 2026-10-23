# Map: BESS efficiency run (RTE at the point of connection)

**Label:** wayfinder:map

## Destination

A spec at `.scratch/rte-efficiency/spec.md`, ready to hand to implementation: an engine module
that takes an ambient-temperature time series (15-min or hourly) and a catalogue BESS solution
and writes, per timestamp, the **operating** round-trip efficiency of an efficiency run and the
**idle** standby loss, both as percentages at the point of connection.

## Notes

- Domain: `CONTEXT.md` (see **Efficiency run**, **Auxiliary consumption**, and the separate
  worst-case **Auxiliary load**, which stays a sizing figure only) and `docs/adr/`. ADR-0004
  (ratings per ambient, never interpolated) sets a precedent any curve-lookup decision must
  confront explicitly.
- Every session consults the `grilling` and `domain-modeling` skills.
- Settled framing (charting session, 2026-10-09):
  - Input: `timestamp, ambient °C`; everything else is static configuration. Output CSV:
    `timestamp, operating RTE %, idle loss %, PCS power % of rated`. First interface is a
    Python function / CLI.
  - Efficiency run: full charge then full discharge at rated power for the declared discharge
    duration, the whole cycle at that timestamp's ambient; unity power factor at the POC.
    Electrical losses are evaluated at the full power available at that ambient (rated, or
    derated when PCS derating applies).
  - Idle figure: auxiliary consumption plus energised-transformer no-load losses, as % of
    nameplate energy per hour.
  - Auxiliary consumption is fed from the MV busbar and counts on both legs at the POC (adds to
    import when charging, reduces export when discharging). It is supplied separately from the
    design's losses.
  - Transformer and cable losses come from an actual design when one is given, otherwise from
    typed-in fixed loss percentages.
  - Hot-ambient PCS derating: the run uses the derated power for that ambient, cycling the same
    energy over a longer time.
  - Battery data is tied to a catalogue BESS solution; its manufacturer curves attach to that
    entry.
- Engine boundary from `AGENTS.md`: the module lives in `powertool/`, with no web or UI
  dependency.

## Decisions so far

<!-- one line per resolved ticket: [title](issues/NN-slug.md): gist -->

- [Collect the manufacturer curves](issues/01-collect-manufacturer-curves.md): Sungrow PT3 (ST6900UX-4H) aux consumption per container at 1 and 2 cycles/day and per MVS (banded), operating and standby, plus a −30…50 °C active-power derating curve; no efficiency figures.
- [Does ambient temperature change a containerised battery's DC efficiency?](issues/02-dc-efficiency-vs-ambient.md): barely while cells are in band; model DC RTE as one ambient-independent value per BESS solution and put all ambient dependence in auxiliary consumption.
- [Which losses sit between the battery and the POC, from a design and without one?](issues/03-loss-chain.md): existing engine losses, symmetric in direction, PV at zero; discharge anchored at DC output, charge at a POC-capacity import; aux on the MV busbar; without a design, typed-in load %, no-load % and POC capacity.
- [How does PCS derating reshape an efficiency run?](issues/04-derated-efficiency-run.md): energy fixed, cycle stretches; legs run at derated power (charge imports the lesser of POC capacity and what the derated PCS takes); aux as published; derating is never a loss but a fourth output column, `PCS power % of rated`.
- [How does cycles per day enter the efficiency run?](issues/05-cycles-per-day.md): one required static parameter selecting the container aux table; linear between published references, nearest table outside (and for single-reference solutions) with a warning; operating/standby are average draw per unit in that state; CSV unchanged.
- [How do auxiliary-consumption tables and the derating curve attach to the catalogue and get looked up?](issues/06-curve-storage-and-lookup.md): inline simulated parameters on the BESS solution and station transformer; efficiency curves interpolate (ADR-0009), bands step, ratings stay lookup-only; clamp out-of-range ambient with a warning; missing container aux is an error; without a design the caller types solution, station transformer, station and container counts.
- [Get Sungrow's reference efficiency figures for ST6900UX-4H](issues/07-reference-rte-figure.md): one-way conversion efficiency DC terminals → MVS LV 98.4 % per leg (four published items), excluding cells and aux; cell DC RTE unpublished, default 95 % (project assumption, overridable); MVS aux adds to transformer losses; table definitions not obtained.
- [How do cell efficiency, conversion efficiency and the loss chain combine into one RTE?](issues/08-energy-accounting.md): rated active power Pn (1724 kW) at the AC terminals; cycle the nominal energy at DC, discharging at Pn × derating at AC (~3.94 h); cell RTE applied once on the charge leg so the cycle closes; constant 98.4 % each way; RTE = POC export ÷ POC import, no time stepping. Pn in sizing split out to [Should sizing use rated active power?](issues/09-rated-active-power-in-sizing.md).

- [What exactly goes into the idle standby loss?](issues/10-idle-figure.md): POC import in kWh per idle hour (was % of nominal energy per hour until 2026-10-23); container and MVS standby aux plus no-load of every station and HV transformer (in full in a hybrid); PCS standby inside Sungrow's standby aux; no load losses on the idle draw; no cell self-discharge; independent of derating.
- [Should sizing use rated active power?](issues/09-rated-active-power-in-sizing.md): yes; Pn is the active limit in the PCS check and the seed, kVA stays the apparent limit (ADR-0008 amendment); missing Pn is an error everywhere, which blocks ST6680UX-2H until Sungrow supplies it; sizing change built on its own branch before the spec.
- [Discharge above the POC capacity](issues/11-discharge-above-poc-capacity.md): discharge export is capped at the POC capacity; the containers run below Pn and the leg stretches.

## Not yet specified

- **Time-series edge cases** (deferred by the owner, 2026-10-23): resolution detection, gaps,
  timezone/DST. Rows are evaluated independently, so these affect input validation only
  (out-of-range ambients are settled: clamp and warn).

[spec.md](spec.md) is written (2026-10-23) with a worked example.

## Out of scope

- Degradation and augmentation (capacity fade and RTE drift over life): a separate, related
  module. This effort models beginning of life only.
- Dispatch or energy management: the downstream model decides when the battery charges,
  discharges or idles.
- Non-unity power factor at the POC.
- API and UI exposure: a later effort once the engine module exists.

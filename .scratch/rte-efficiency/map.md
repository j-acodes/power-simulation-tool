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
    `timestamp, operating RTE %, idle loss %`. First interface is a Python function / CLI.
  - Efficiency run: full charge then full discharge at rated power for the declared discharge
    duration, the whole cycle at that timestamp's ambient; unity power factor at the POC.
    Electrical losses are evaluated at full power only (the battery always runs at full power).
  - Idle figure: auxiliary consumption plus energised-transformer no-load losses, as % of
    nameplate energy per hour.
  - Auxiliary consumption is fed from the MV busbar and counts on both legs at the POC (adds to
    import when charging, reduces export when discharging). It is supplied separately from the
    design's losses.
  - Transformer and cable losses come from an actual design when one is given, otherwise from
    typed-in fixed loss percentages.
  - Hot-ambient PCS derating: the run uses the derated power for that ambient (which stretches
    the cycle).
  - Battery data is tied to a catalogue BESS solution; its manufacturer curves attach to that
    entry.
- Engine boundary from `AGENTS.md`: the module lives in `powertool/`, with no web or UI
  dependency.

## Decisions so far

<!-- one line per resolved ticket: [title](issues/NN-slug.md): gist -->

- [Collect the manufacturer curves](issues/01-collect-manufacturer-curves.md): Sungrow PT3 (ST6900UX-4H) aux consumption per container at 1 and 2 cycles/day and per MVS (banded), operating and standby, plus a −30…50 °C active-power derating curve; no efficiency figures.
- [Does ambient temperature change a containerised battery's DC efficiency?](issues/02-dc-efficiency-vs-ambient.md): barely while cells are in band; model DC RTE as one ambient-independent value per BESS solution and put all ambient dependence in auxiliary consumption.

## Not yet specified

- **Energy accounting inside the run**: which power is "rated" (PCS AC output or POC), how the
  charge leg tops up the energy the discharge leg delivers, and how DC and PCS efficiencies
  combine with the loss chain. Firms up after the loss-chain decision and Sungrow's reference
  efficiency figures.
- **Idle details**: which transformers count as energised when idle, and whether PCS standby
  draw is separate from auxiliary consumption.
- **Time-series edge cases**: resolution detection, gaps, timezone/DST (out-of-range ambients belong to [How do auxiliary-consumption tables and the derating curve attach to the catalogue and get looked up?](issues/06-curve-storage-and-lookup.md)).
- **Spec assembly**: write `spec.md` from the decisions, with acceptance criteria and a worked
  example.

## Out of scope

- Degradation and augmentation (capacity fade and RTE drift over life): a separate, related
  module. This effort models beginning of life only.
- Dispatch or energy management: the downstream model decides when the battery charges,
  discharges or idles.
- Non-unity power factor at the POC.
- API and UI exposure: a later effort once the engine module exists.

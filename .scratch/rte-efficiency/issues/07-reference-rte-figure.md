# Get Sungrow's reference efficiency figures for ST6900UX-4H

**Type:** task (HITL)
**Status:** claimed
**Blocked by:** None

## Question

The curves give auxiliary consumption and derating but no efficiency. Ask Sungrow (datasheet,
technical proposal, or the account engineer) for: round-trip efficiency of the container and
which boundary it is measured at (DC, AC terminals of the integrated PCS, MV side of the MVS),
whether it includes auxiliary consumption, and the test conditions (C-rate, SOC window,
temperature). If only separate figures exist, ask for DC RTE and PCS efficiency at rated power.
Resolved when the figure(s) and their boundary are recorded; if Sungrow gives nothing, record
that, and the efficiency run falls back to a typed-in value (see the DC-efficiency research
answer).

## Comments

- 2026-10-13, from [How does cycles per day enter the efficiency run?](05-cycles-per-day.md):
  also ask Sungrow to confirm what Tables 7–9 mean by operating and standby power. The run
  assumes the average draw per container (per MVS for Table 9) over the time spent in that
  state; confirm it is not a peak, and what period the cycles-per-day reference assumes.
- 2026-10-13, consolidated ask list sent to the user for Sungrow:
  1. Container RTE: value, boundary (DC, PCS AC terminals, MV side of the MVS), whether it
     includes auxiliary consumption, test conditions (0.25P, SOC window, temperature, BOL).
  2. If no system figure: DC RTE, and PCS efficiency at rated power (ideally vs load, both
     directions).
  3. Tables 7–9: average or peak; per container / per MVS; what duty the 1 and 2 cycles/day
     references assume; whether standby includes PCS standby draw; whether the MVS figures
     include transformer no-load losses.
  4. Behaviour outside −30…50 °C, and why the datasheet's operating range stops at 45 °C while
     the derating curve runs to 50 °C.
  5. MVS7400-LS load and no-load losses (the catalogue's `pk_kw` and `p0_kw` are placeholders).

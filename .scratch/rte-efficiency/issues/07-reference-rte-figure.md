# Get Sungrow's reference efficiency figures for ST6900UX-4H

**Type:** task (HITL)
**Status:** resolved
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


## Answer

Resolved 2026-10-13 from figures the user obtained from Sungrow
(`data/manufacturer-curves/sungrow-pt3/parameters-lv-losses.png`).

1. **One-way conversion efficiency, DC terminals to MVS LV terminals: 98.4 %**, applied on each
   leg (charge and discharge). It is the product of four published items:

   | Item | Efficiency |
   |---|---|
   | DC cable | 99.90 % |
   | PCS bus losses | 99.95 % |
   | PCS | 98.70 % |
   | LV cable, PCS to MV transformer | 99.90 % |
   | **Product** | **98.45 %** (Sungrow quotes 98.4 %) |

   It excludes the cells and auxiliary consumption; the round trip through conversion alone is
   about 96.9 %. Store the four items, not only the product.
2. **Cell (DC) round-trip efficiency: not published.** The BESS solution carries a default of
   95 %, overridable per run. It is a project assumption, not Sungrow data, and the catalogue
   must say so beside the value. This takes the "else typed in" branch of
   [Does ambient temperature change a containerised battery's DC efficiency?](02-dc-efficiency-vs-ambient.md)
   with a stated default.
3. **MVS auxiliary consumption (Table 9) adds to the transformer's load and no-load losses**
   in the loss chain; it does not replace them. Real MVS7400-LS load and no-load losses are not
   pursued for this effort: the catalogue placeholders stand.
4. **Above 50 °C:** clamp and warn stands (user decision); Sungrow's behaviour there is not
   pursued.
5. **Not obtained:** what Tables 7–9 mean by operating and standby, the duty behind the
   cycles-per-day references, and whether standby includes PCS standby draw. The definitions
   assumed in [How does cycles per day enter the efficiency run?](05-cycles-per-day.md) stand.

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

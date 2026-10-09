# Collect the manufacturer curves

**Type:** task (HITL)
**Status:** resolved
**Blocked by:** None

## Question

Which manufacturer curves do we actually have for the target BESS solution(s)? Gather the files
into `data/manufacturer-curves/<supplier>/` (any format: PDF, XLSX, CSV, images). At minimum
look for:

- auxiliary consumption vs ambient temperature, operating and idle
- PCS power derating vs ambient temperature
- PCS efficiency (at rated power, or vs load)
- DC / battery round-trip efficiency, if published (vs temperature, C-rate or SOC)

Resolved when the files are in the repo; the answer records what each file contains (axes,
units, operating points, which product and model number it covers) and what is missing.

## Answer

Collected in `data/manufacturer-curves/sungrow-pt3/` (PNG extracts of Sungrow tables/figures).
All cover PowerTitan 3.0 at 0.25P, i.e. catalogue BESS solution **ST6900UX-4H**; the MVS table
matches its station transformer **MVS7400-LS**.

| File | Content | Axes / units |
|---|---|---|
| `aux-curve-1cycle.png` | Table 7: auxiliary consumption per battery container, reference **1 cycle/day** | ambient −30, −10, 0, 15, 25, 35, 45, 50 °C → operating kW, standby kW |
| `aux-curve-2cycles.png` | Table 8: the same at reference **2 cycles/day** | same points |
| `aux-curve-mvs.png` | Table 9: auxiliary consumption per MVS | three ambient **bands** [−30,10), [10,35), [35,50] °C → operating kW, standby kW |
| `t-derating-p.png` | Fig. 2-4: active-power temperature derating | 1.0 Pn from −30 to 45 °C, linear to 0.6 Pn at 50 °C (−0.08 Pn/°C), symmetric for charge and discharge |

Transcribed values (kW per container, operating / standby):

| °C | 1 cycle/day | 2 cycles/day |
|---|---|---|
| −30 | 4.63 / 12.30 | 4.63 / 11.23 |
| −10 | 5.32 / 10.55 | 5.32 / 10.60 |
| 0 | 5.32 / 5.10 | 5.32 / 5.24 |
| 15 | 11.15 / 4.10 | 11.40 / 5.00 |
| 25 | 12.90 / 4.10 | 12.90 / 6.20 |
| 35 | 17.70 / 8.25 | 17.70 / 9.60 |
| 45 | 20.40 / 10.00 | 21.00 / 12.52 |
| 50 | 19.90 / 16.50 | 17.46 / 17.60 |

MVS (kW per MVS, operating / standby): [−30,10) 3.50 / 2.50; [10,35) 4.02 / 2.76;
[35,50] 4.02 / 3.02.

Observations that later tickets depend on:

- Auxiliary consumption depends on **cycles per day** as well as ambient and state, a dimension
  the efficiency run did not have.
- Standby exceeds operating below 0 °C (idle containers must heat; operating cells self-heat).
- Operating draw falls from 45 to 50 °C, plausibly because derated power generates less heat.
- The container tables are point values; the MVS table is banded (a step lookup by design).
- The derating figure is container-level active power (PCS integrated), defined only from
  −30 to 50 °C.
- **Missing:** any DC or AC round-trip efficiency figure, PCS efficiency, and behaviour outside
  −30…50 °C.

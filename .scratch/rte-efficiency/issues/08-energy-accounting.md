# How do cell efficiency, conversion efficiency and the loss chain combine into one RTE?

**Type:** grilling
**Status:** resolved
**Blocked by:** 03, 04, 07

## Question

The legs' anchors are settled (discharge at the DC output at rated or derated power, charge at
a POC-capacity import). Settle the energy accounting inside the efficiency run: which energy
the run cycles, how the charge leg tops up what the discharge leg delivers, where the cell DC
RTE (default 95 %) and the one-way conversion efficiency (98.4 %, DC terminals to MVS LV) apply,
and how the operating RTE at the POC is computed from the two legs.

## Answer

Resolved by grilling, 2026-10-14.

1. **Rated active power.** The run uses Pn, the container's rated active power at its AC
   terminals (MVS LV side): 1724 kW for the ST6900UX-4H, from Sungrow's system curve
   (`TI_20250915_ST6900UX-4H_System Curve_V1_EN`, Tab. 1-1; 1800 kVA apparent). It becomes a
   simulated parameter on the BESS solution. The derating curve is a fraction of this Pn.
   Bringing Pn into sizing, which treats the PCS kVA as both limits (ADR-0008), is left to
   [Should sizing use rated active power?](09-rated-active-power-in-sizing.md).
2. **Cycled energy and discharge anchor.** The run cycles the nominal energy (containers ×
   6904 kWh) at the DC terminals. The discharge leg runs at Pn × derating factor at the AC
   terminals, so the DC side runs at Pn ÷ 0.984 and the leg lasts about 3.94 h when not derated.
   Delivering Pn × 4 h at AC would need about 7008 kWh from 6904 kWh of cells; the declared
   4 h is nameplate arithmetic (nominal energy ÷ Pn) and stays the catalogue nameplate. This
   moves the discharge anchor of
   [Which losses sit between the battery and the POC, from a design and without one?](03-loss-chain.md)
   and [How does PCS derating reshape an efficiency run?](04-derated-efficiency-run.md) from
   the DC output to the AC terminals.
3. **Cell RTE (default 95 %) applies once, on the charge leg.** The charge leg must put the
   discharged energy ÷ cell RTE back in at the DC terminals, so the cycle closes. No per-leg
   split: it gives the same RTE to within about 0.01 point and invents nothing Sungrow did not
   publish.
4. **Conversion efficiency is a constant 98.4 %** per leg at every power level, both
   directions, including part load (POC-limited charge, derating). No load curve is published.
5. **RTE = energy exported at the POC ÷ energy imported at the POC.** Each leg is at constant
   power, so each is its end powers × its duration; auxiliary consumption and no-load losses
   run over each leg's own duration. The run starts empty, with no rest between legs. No time
   stepping.

Worked core, one container, before the loss chain and auxiliary consumption: discharge
6904 kWh DC → 6794 kWh AC; charge 6904 ÷ 0.95 = 7267 kWh DC ← 7385 kWh AC; RTE at the AC
terminals 6794 ÷ 7385 = 92.0 % (= 0.95 × 0.984²).

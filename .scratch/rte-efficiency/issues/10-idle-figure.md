# What exactly goes into the idle standby loss?

**Type:** grilling
**Status:** resolved
**Blocked by:** 03, 05, 06

## Question

The idle figure is auxiliary consumption plus energised-transformer no-load losses, as a
percentage of nameplate energy per hour. Settle which transformers count as energised when
idle (station transformers, HV transformer, in a hybrid too), whether PCS standby draw is
separate from Sungrow's standby auxiliary consumption, whether the idle draw carries
loss-chain losses, and whether the figure is energy imported at the POC or energy drained from
the cells.

## Answer

Resolved by grilling, 2026-10-23.

**Idle loss (% per hour) = idle draw imported at the POC ÷ fleet nominal energy × 100.**

1. **Energised transformers.** Every station transformer and the HV transformer stay
   energised while the battery is idle (hot standby); switching transformers off is not
   modelled. In a hybrid design the HV transformer's no-load loss counts in full against the
   battery, the same PV-at-zero rule as
   [Which losses sit between the battery and the POC, from a design and without one?](03-loss-chain.md).
2. **PCS standby draw** is assumed to sit inside Sungrow's standby auxiliary consumption; there
   is no separate term. The spec records it as an open question for Sungrow.
3. **No loss-chain load losses on the idle draw**, with or without a design. The draw is small
   enough that its own load losses are about 1 % of a figure near 0.1 % per hour.
4. **Imported at the POC, not drained from the cells.** The grid supplies auxiliaries and
   transformer magnetising while the battery is idle, matching the POC-to-POC boundary of the
   operating RTE. The downstream model should treat the idle figure as grid import, not a fall
   in state of charge.
5. **Cell self-discharge is out of scope.** It is unpublished, around 0.003 % per hour for LFP,
   and a state-of-charge quantity rather than a POC import.
6. **Denominator:** the fleet's nominal energy at the DC terminals (containers × 6904 kWh for
   the ST6900UX-4H), the energy the efficiency run cycles. The figure does not depend on PCS
   derating, since idle moves no power.
7. **Without a design**, the typed-in no-load loss is a percentage of the fleet's rated active
   power (containers × Pn, 1724 kW each), unaffected by derating.

The idle draw at a timestamp's ambient is the sum of:

- container standby auxiliary consumption × container count, from the container table
  interpolated in ambient and cycles per day
  ([How do auxiliary-consumption tables and the derating curve attach to the catalogue and get looked up?](06-curve-storage-and-lookup.md));
- MVS standby auxiliary consumption × station count, from the band containing the ambient;
- no-load losses of every station transformer and the HV transformer (the design's catalogue
  `p0`), or the typed-in no-load percentage without a design.

Out-of-range ambient clamps with a warning, as for the operating figure.

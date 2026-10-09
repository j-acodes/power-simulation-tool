# How does PCS derating reshape an efficiency run?

**Type:** grilling
**Status:** resolved
**Blocked by:** 01

## Question

When the PCS derating curve caps power below rated at a timestamp's ambient, the run uses the
derated power. Decide what stays fixed and what stretches: is the energy cycled still the
declared-duration energy (longer cycle), or the duration fixed (less energy)? How do auxiliary
consumption over the longer cycle and the loss chain at reduced power enter? Does the output
flag derated timestamps? Depends on the actual shape of the derating curves.

From the loss-chain decision: the charge leg imports the POC capacity, which assumes PCS power
is above it. Derating can take PCS power below the POC capacity (0.6 Pn at 50 °C); decide what
the charge leg imports then.

## Answer

Resolved by grilling, 2026-10-09. The Sungrow PT3 curve derates only from 45 to 50 °C
(1.0 Pn to 0.6 Pn, symmetric); behaviour outside −30…50 °C belongs to
[How do auxiliary-consumption tables and the derating curve attach to the catalogue and get looked up?](06-curve-storage-and-lookup.md).

1. **Energy fixed, cycle stretched.** A derated run still cycles the declared energy (rated
   power × declared duration) at the derated power, so it takes longer. Derating limits power,
   not energy.
2. **Charge leg:** imports the lesser of the POC capacity and the import that drives the PCS at
   its derated power (derated power plus loss chain plus auxiliary consumption). Without
   derating the POC capacity is always the lesser, so the loss-chain rule is unchanged.
3. **Discharge leg:** anchored at the DC output at derating factor × rated power, with the same
   flow out to the POC. Derating is never counted as a loss in the RTE: the downstream model
   would read a power limit as lost energy and corrupt its state of charge. The power limit
   travels separately (item 6).
4. **Auxiliary consumption:** the table's operating kW at that ambient, as published, over the
   whole stretched cycle, with no scaling by power. The drop from 45 to 50 °C suggests the
   tables already reflect derated operation; scaling would count it twice.
5. **Loss chain:** evaluated at the full power available at that ambient (the derated power when
   derated); load losses fall with power, no-load losses run over the longer cycle.
6. **Output:** a fourth column, `PCS power % of rated` (100 when not derated), one figure for
   both directions since the curve is symmetric. The downstream model reads it as a
   per-timestamp power cap. The idle figure is unaffected.

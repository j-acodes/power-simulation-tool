# Open question: the switchgear's cable entry may be the real limit

**Raised:** 2026-09-21, by the owner, after ticket 02 landed and before ticket 03 started.
**Status:** needs-info — blocks the decision on ticket 03's scope, not ticket 03's code.

## The observation

The 630 A switchgear rated current gives circuit ceilings that are too generous against
industry practice. At 30 kV it allows 32.7 MVA; the owner is used to seeing 20-21 MVA
(~400 A) as a maximum for a 30 kV circuit. At 20 kV the figure of 21.8 MVA is close to
that intuition, so the discrepancy grows with voltage.

Investigated this session: short-circuit current is **not** the cause. Short-time withstand
(20 kA/1 s on the catalogue's RMUs, 20 kA/3 s on the BESS ones) is a fault-level check against
the HV/MV transformer's infeed and does not scale with circuit loading. The cable adiabatic
check sets a minimum conductor and screen cross-section, which is a floor on the cable, not a
ceiling on the circuit.

## The owner's hypothesis

The binding limit is the **cable entry into the switchgear**, not the switchgear's own rated
current. A feeder compartment accepts a bounded number of cables per phase and a bounded
maximum cross-section per cable. If a given RMU accepts one 240 mm2 cable per phase, then that
cable's ampacity — not the 630 A busbar figure — is what bounds the circuit, and parallel trunk
runs are not physically available at all.

This also reframes the parallel-cable behaviour the spec currently calls "expected, not a
defect": the engine adds parallel runs freely, but real hardware may have nowhere to land them.

## What this would need

- The switchgear becomes something the tool **sizes**, not just reads a rating off.
- Two new datasheet parameters per transformer station, per feeder: **cables accepted per phase**
  and **maximum cable cross-section**. Both are supplier-published and neither is in the
  catalogue today.
- The circuit bound becomes the lesser of the switchgear rated current and what the admissible
  cable entry can carry.

## Relationship to the existing plan

Ticket 03 (retire the flat 400 A cap, group by switchgear) is written and ready. The question is
whether to ship it first and add the cable-entry bound as its own unit, or to re-spec 03 so that
no intermediate state produces circuits nobody would build. Not decided.

Also still unmodelled and separately scoped: installation derating of cable ampacity. The
catalogue's figures assume direct burial, single circuit, ~1.0 K.m/W soil; the 0.80
`max_utilization` is a design margin, not a derating factor.

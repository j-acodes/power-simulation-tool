# PCS rating governs BESS conversion, and the seed sizes container counts to energy

A BESS station's pairing used to fix its container count: the MVS7400-LS served four
ST6900UX-4H containers, every station was full, and nothing computed the count. The pairing
figure is now a **maximum**. When the seed wizard proposes a BESS fleet it sizes stations to
point-of-connection power, then sizes containers to the fleet's energy — power times discharge
duration — filling stations to the maximum in order and leaving the remainder on the last. If
the maximum across the power-sized stations cannot reach the energy, it adds stations until it
can. After seeding the count belongs to the engineer: solving checks it and never recomputes it,
and a count above the pairing maximum is a validation error.

A station holding fewer containers holds less PCS, so its conversion capacity is no longer its
transformer station's rating. BESS duty is therefore allocated between stations in proportion to
installed PCS apparent power — containers × PCS units per container × PCS kVA — and the
transformer station is checked separately against its own AC power at ambient and the BESS
maximum-loading limit. This is ADR-0005's rule for PV inverters applied to the PCS, and it is
read the same way: one PCS figure is both the active limit in kW and the apparent limit in kVA,
checked independently at 100% of installed PCS, and a PCS failure is a warning, not a refusal
to solve. The PCS publishes no ambient dependence, so there is no ambient lookup.

## Considered Options

- **Keep the count fixed and oversize stations to meet energy.** Rejected: it buys whole
  stations, transformers and feeders to close a shortfall a few containers would close.
- **Let the seed trim containers but keep allocation by transformer rating.** Rejected: a
  station trimmed to one container (1800 kVA of PCS) would still be allocated its full 7400 kVA
  transformer duty and report compliant, which no real site can deliver.
- **Let the count exceed the pairing.** Rejected: the pairing is the supplier's statement of
  what fits behind a transformer; exceeding it invents a configuration nobody sells.

## Consequences

Every BESS and hybrid result shifts, full stations included, because allocation now reads PCS
(4 × 1800 = 7200 kVA) rather than transformer rating (7400 kVA). Saved designs whose container
override exceeds the pairing stop solving until corrected.

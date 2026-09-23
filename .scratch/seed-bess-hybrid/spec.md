# Spec: Seed BESS and hybrid plants, with PCS-governed BESS allocation

Status: ready-for-agent

Decisions: ADR-0008 (PCS governs BESS conversion; seed sizes container counts). Respects
ADR-0001 (hybrid topology), ADR-0002 (declared technology), ADR-0005 (the PV rule ADR-0008
mirrors), ADR-0007 (busbar planning).

## Problem Statement

A sizing engineer can ask the seed wizard to propose a starting diagram only for a PV plant. A
BESS or hybrid design must be drawn station by station, with the station count, the container
count behind each station and the discharge duration worked out by hand.

Separately, the engine shares BESS duty between stations by transformer-station rating and never
checks the PCS. Every station has been full, so this has not mattered — but once a station holds
fewer containers than its pairing allows, it would be allocated duty its PCS cannot convert and
still report compliant. A container count above the pairing maximum is also accepted today.

## Solution

The seed wizard follows the design's declared technology. A PV design sees today's wizard. A BESS
design sees a BESS section: discharge duration, then a BESS solution that sells it, then a station
model paired with that solution. A hybrid design sees both sections.

For a BESS fleet the seed sizes the station count to point-of-connection BESS power, then sizes
containers to the fleet's energy (power × discharge duration): stations are filled to the pairing
maximum in order and the remainder is left on the last one. If the power-sized stations at the
maximum cannot reach the energy, stations are added until they can. The chosen duration is written
into the design's discharge duration setting.

BESS duty is shared between stations in proportion to installed PCS apparent power (containers ×
PCS units per container × PCS kVA). PCS active and apparent limits are checked at 100% as
warnings; the transformer station is checked separately against its AC power at ambient and the
BESS maximum-loading limit. A container count above the pairing maximum is a validation error.

## User Stories

1. As a sizing engineer on a BESS design, I want the seed wizard to show only BESS inputs, so that the interface matches the declared technology.
2. As a sizing engineer on a hybrid design, I want the wizard to show a PV section and a BESS section, so that I can seed both fleets at once.
3. As a sizing engineer on a PV design, I want the wizard to behave exactly as before, so that nothing I rely on changes.
4. As a sizing engineer, I want to pick a discharge duration first, so that I am only offered BESS solutions that sell it.
5. As a sizing engineer, I want to be offered only station models paired with the chosen BESS solution, so that I cannot seed an unsellable combination.
6. As a sizing engineer, I want to enter BESS power at the point of connection, so that the fleet is sized to the grid requirement.
7. As a sizing engineer, I want the station count sized to BESS power, so that the fleet can deliver the point-of-connection power after losses.
8. As a sizing engineer, I want container counts sized to power × discharge duration, so that the seeded plant meets its energy check.
9. As a sizing engineer, I want stations filled to the pairing maximum in order with the remainder on the last, so that most stations share one configuration.
10. As a sizing engineer, I want the seed to add stations when full stations still fall short on energy, so that the seeded plant never fails its own energy check.
11. As a sizing engineer, I want the chosen discharge duration saved into the design, so that the energy check runs immediately.
12. As a sizing engineer on a hybrid design, I want to enter PV and BESS power separately, so that the point of connection carries one figure per fleet.
13. As a sizing engineer on a hybrid design, I want a maximum-loading limit per fleet, so that each fleet's duty cycle is respected.
14. As a sizing engineer on a hybrid design, I want trunk length and station spacing per fleet, so that a compact BESS yard is not given PV-field cable lengths.
15. As a sizing engineer on a hybrid design, I want one export cable length and one feeders-per-busbar setting, so that shared equipment is described once.
16. As a sizing engineer on a hybrid design, I want the substation auxiliary load drawn on the first PV busbar, so that it enters the power balance once.
17. As a sizing engineer on a BESS design, I want the substation auxiliary load drawn on the BESS busbar.
18. As a sizing engineer on a hybrid design, I want PV drawn on the left and BESS on the right under a centred point of connection, so that the proposal is readable.
19. As a sizing engineer, I want a seeded BESS or hybrid plant to validate and solve with every fleet within its loading limit, so that the proposal is a sound starting point.
20. As a sizing engineer, I want to reduce a station's container count after seeding and have solving keep my number, so that partial population stays my judgement.
21. As a sizing engineer, I want a container count above the pairing maximum rejected, so that I cannot draw a configuration the supplier does not sell.
22. As a sizing engineer, I want the canvas container input capped at the pairing maximum, so that the limit is visible where I type.
23. As a sizing engineer, I want BESS duty shared by installed PCS, so that a thinly populated station is not credited with power it cannot convert.
24. As a sizing engineer, I want a warning when a station's PCS active or apparent limit is exceeded, so that I see conversion shortfalls without losing the result.
25. As a sizing engineer, I want transformer-station loading still checked separately, so that both pieces of equipment are verified.
26. As a sizing engineer, I want seeding to be deterministic, so that the same inputs always propose the same plant.

## Implementation Decisions

- **Engine (PCS allocation).** The BESS branch of diagram solve allocates duty by installed PCS
  apparent power per station, exactly as the PV branch allocates by installed inverter power
  (ADR-0005). The existing optional per-station allocation-capacity input to the manual arranger
  is the intended carrier. One PCS kVA figure is both the kW and kVA limit; active and apparent
  checks are independent warnings (not errors), with no ambient lookup. Transformer losses and
  loading use the allocated duty and the BESS maximum-loading limit, unchanged.
- **Validation.** A container override greater than the pairing's count for the station's chosen
  solution is an error-severity issue on that station. The pairing figure is now a maximum; a
  station without an override remains full at it.
- **Seed request contract.** The seed request gains the design's technology and a BESS block.
  PV fields become required only when technology permits PV; BESS fields only when it permits
  BESS. BESS block: point-of-connection BESS power (MW), discharge duration (h), BESS solution key,
  station model key, maximum loading, trunk length, spacing. The PV block keeps today's fields plus
  per-fleet trunk/spacing/loading for hybrid. Export length, interconnection, voltages, power-factor
  target, auxiliary load and feeders-per-busbar stay shared. The request validator rejects a
  solution that does not sell the duration and a station not paired with the solution.
- **BESS seed sizing.** Station count: fixed point on power using per-station installed PCS at
  the pairing maximum, as the PV seed does with inverter capacity. Containers: required = ceil(P_bess ×
  duration ÷ energy per container); if required > stations × maximum, raise the station count to
  ceil(required ÷ maximum). Fill stations in circuit order to the maximum, remainder on the last,
  written as the station's container override only where it differs from the maximum.
- **Hybrid seed.** Each fleet is sized and arranged as its own cascade with its own busbar(s);
  both hang off the one shared HV transformer (or point of connection for MV). The resulting
  diagram must pass the real multi-branch solve with both fleets within limits; if the per-fleet
  Stage-1 estimate undersizes a fleet against the shared-loss solve, the seed iterates on that
  fleet's count.
- **Diagram output.** Point of connection carries both fleet power figures; rules carry per-kind
  maximum loading and the discharge duration; BESS busbar(s) and stations carry fleet kind `bess`.
  Layout: PV left, BESS right, POC/HV centred.
- **Frontend.** The wizard reads the design's declared technology and renders the PV section, the
  BESS section, or both. BESS selectors cascade duration → solution → station. The canvas container
  input is capped at the pairing maximum.

## Testing Decisions

- Test external behaviour only: seed parameters in → diagram out → validate and solve that diagram;
  drawn diagram in → results and issues out; wizard rendered for a technology → which inputs show.
- Seams: the seed function and its API route (prior art: the PV seed tests); diagram solve and
  validation (prior art: the hybrid tests); the wizard component (prior art: its existing test).
- The golden baseline is refreshed once, in the cutover ticket, with the shifted BESS numbers
  explained; a hybrid with zero BESS power must still reproduce PV-only exactly.

## Out of Scope

- Per-ambient PCS ratings; PCS power-factor limits.
- Seeding designs with more than one station model per fleet.
- Changing the PV seed's behaviour for PV-only designs.
- Recomputing container counts during solve.

## Further Notes

Existing BESS and hybrid results shift (a full MVS7400-LS station is allocated as 7200 kVA of PCS,
not 7400 kVA of transformer). Saved designs with an override above the pairing stop solving.
The database is reset only with the owner's explicit authorization.

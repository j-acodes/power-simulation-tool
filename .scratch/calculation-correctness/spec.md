# Spec: Calculation correctness at the converged operating point

Status: ready-for-agent

## Problem Statement

The diagram solve currently refines the active delivery target by scaling branch
active output until the requested active power reaches the point of connection
(POC). Reactive power is scaled as a side effect, but the resulting reactive
duty is not checked against the duty implied by the requested POC power factor.
For example, a 3 MW design at power factor 0.95 has required reactive duty of
approximately 986.05 kvar, while the current path reports approximately 964.43
kvar. The result can therefore look compliant while failing the one physical
connection's active-and-reactive requirement.

The refinement also builds plant layout, cable selections, loading, currents,
losses, and compliance flags before the final operating point is known. A
correction can cross a cable ampacity/utilization or loss threshold, or a
loading/current threshold, after those values were computed. The result mapper
can consequently expose a refined active figure alongside stale reactive,
station, cable, or loss figures.

This is a correctness defect at the diagram solve boundary. It affects PV-only,
BESS-only, and hybrid designs, while the physical model remains one POC with
shared export equipment.

## Solution

Make loss refinement converge on the complete operating point required at the
single physical POC: active delivery and the reactive duty implied by the POC's
requested power factor. Recompute or revalidate every continuous quantity and
every loading, current, cable, loss, and power-balance check from that same
converged operating point before returning results.

For a hybrid design, retain one shared HV export step and one combined POC
requirement. Split reactive duty between the PV and BESS fleets pro-rata by
active power, as required by ADR-0001. This does not turn the fleets into two
independent POC power-factor obligations.

Preserve the existing diagram input and solve response contracts. Existing
drawings, including single-fleet payloads and harmless unknown properties, must
continue to validate, solve, or report the same class of issue. A failed or
non-convergent refinement must remain an explicit solve issue with no partial
results.

## User Stories

1. As a sizing engineer, I want a PV fleet's solved POC delivery to meet both the requested active power and its requested power-factor reactive duty, so that the design represents the grid requirement rather than only its real-power component.
2. As a sizing engineer, I want a BESS fleet's solved POC delivery to meet the same active-and-reactive requirement, so that storage sizing is not less rigorous than PV sizing.
3. As a sizing engineer, I want a hybrid plant to satisfy one combined POC requirement, so that the result matches one physical interconnection agreement.
4. As a sizing engineer, I want the hybrid reactive duty split pro-rata by fleet active power, so that each fleet carries its physical share of the shared requirement.
5. As a sizing engineer, I do not want each fleet independently forced to meet the POC power factor, so that the solver does not invent two grid connections behind one POC.
6. As a sizing engineer, I want refinement to account for active and reactive losses together, so that transformer, cable, auxiliary, and export losses influence both required inverter/PCS P and Q.
7. As a sizing engineer, I want the reported P, Q, and apparent power at the POC, busbars, stations, circuits, and export equipment to describe one operating point, so that I can reconcile the result without mixing iterations.
8. As a sizing engineer, I want the reported power factor to be derived from the converged P and Q, so that it cannot silently describe an earlier pass.
9. As a sizing engineer, I want cable selections to be made or revalidated using converged local P/Q/S flow, so that a correction cannot leave an undersized cable certified.
10. As a sizing engineer, I want cable utilization, ampacity, voltage/loss-budget checks, and their warning states evaluated at converged flow, so that threshold crossings are visible.
11. As a sizing engineer, I want every station current and loading figure evaluated at converged station duty, so that station compliance is not based on Stage-1 values.
12. As a sizing engineer, I want every circuit trunk current and current-limit check evaluated at converged flow, so that a circuit that crosses its limit is reported as failing.
13. As a sizing engineer, I want fleet loading and loading-limit checks evaluated after refinement, so that the design cannot be marked compliant before its final demand is known.
14. As a sizing engineer, I want collection and export loss totals, per-element loss rows, and power-balance checks to use the same converged flow, so that totals and detail add up.
15. As a sizing engineer, I want auto-selected cables and shared HV export equipment to remain internally consistent with the final apparent power, so that equipment ratings and losses describe the equipment actually reported.
16. As a sizing engineer, I want forced cable choices that become non-compliant after refinement to produce a clear engine issue, so that the editor never presents an invalid forced choice as successful.
17. As a sizing engineer, I want a correction that changes a discrete cable choice or arrangement-dependent threshold to be iterated or rejected explicitly, so that discrete decisions are not frozen from an obsolete operating point.
18. As a sizing engineer, I want convergence to be bounded and deterministic, so that difficult designs return a clear non-convergence issue instead of plausible stale numbers.
19. As a sizing engineer, I want failed refinement to return no partial result through the diagram solve interface, so that downstream UI and API consumers cannot accidentally render mixed or uncertified values.
20. As a sizing engineer, I want a single-fleet design with the other fleet absent or zero-target to retain its existing physical behavior, so that hybrid plumbing does not perturb PV-only or BESS-only work.
21. As a sizing engineer, I want a hybrid design with both fleets active to retain one busbar and cascade per fleet, so that the fleet-level loading and circuit rules remain distinct.
22. As a frontend consumer, I want existing result fields and diagram element mappings to remain available with their current meanings, so that the editor does not need a breaking contract migration.
23. As an API consumer, I want valid diagrams to keep returning HTTP success with the existing issue/results envelope, so that correctness changes do not become transport failures.
24. As an API consumer, I want malformed drawings and engine failures to retain structured issue codes and messages, so that callers can distinguish validation from convergence failure.
25. As a sizing engineer, I want stale or unknown diagram properties to remain harmless where the current permissive contract allows them, so that older saved drawings remain backward compatible.
26. As a reviewer, I want a threshold-crossing case in the solve tests, so that the suite proves checks are performed after refinement rather than merely asserting ordinary values.
27. As a reviewer, I want single-fleet PV, single-fleet BESS, and active hybrid solve cases, so that the accepted topology is covered at the highest observable seam.
28. As a reviewer, I want a non-convergence or forced-capacity failure case, so that the failure contract is tested as deliberately as the success contract.
29. As a reviewer, I want result-consistency assertions tying summary, fleet, node, edge, and loss details to the converged engine state, so that mapping regressions are caught.
30. As a reviewer, I want the requested POC power factor checked without requiring per-fleet PF compliance, so that tests enforce ADR-0001 rather than accidentally superseding it.

## Implementation Decisions

- The primary seam is the existing diagram solve behavior: validate a legal
  diagram, solve it, and inspect the returned issue/results envelope. Lower-level
  numerical seams may be added only for an edge case that cannot be expressed by
  a valid diagram.
- Treat the POC as the authoritative requirement. At convergence, each fleet
  must still meet its own active-power target at the POC; combined delivered P
  is their sum, and combined delivered Q must satisfy the reactive requirement
  derived from that sum and the requested POC power factor, subject to the
  established sign convention and numerical tolerance. One fleet must not
  conceal another fleet's active-power shortfall.
- Refine the coupled P/Q operating point rather than refining active power and
  treating Q as an unchecked by-product. The implementation may choose the
  numerical update strategy, but it must use the same final P/Q to calculate all
  downstream flows and reported quantities.
- Keep shared export equipment shared. For an HV interconnection, the one
  MV/HV transformer and its export cable are sized and evaluated on combined
  hybrid flow. Do not create one export step per fleet. The known MV-hybrid
  multi-edge topology defect remains outside this spec.
- Keep the ADR-0001 reactive split: hybrid fleet reactive duty is pro-rata by
  active power. A zero-target/absent branch must not change the single-fleet
  result. No fleet-level independent POC PF check is introduced.
- Treat discrete cable selections and any arrangement-dependent calculations as
  part of the converged operating point. Recompute or revalidate them after
  each material correction; if a selection changes, continue until the result
  is stable or report bounded non-convergence.
- Recompute station P/Q/S, transformer losses, station loading and current;
  circuit segment P/Q/S, cable losses, utilization and current; fleet loading;
  shared export transformer/cable values; aggregate loss totals; and all
  compliance booleans from the converged state. Do not splice refined scalar
  fields onto pre-refinement detail objects.
- Preserve positional mapping from drawn circuits/stations/segments to returned
  result elements. Correctness work must not reorder the user's diagram or alter
  node/edge identifiers.
- Preserve the diagram schema, API issue/results envelope, existing result field
  names, permissive unknown-key behavior, and structured engine-error handling.
  New fields are unnecessary unless required to explain convergence; any such
  addition must be backward-compatible and optional.
- Keep auxiliary-load semantics, ambient-rated transformer lookup, declared
  technology, and the existing steady-state sign conventions unchanged.
- Use the existing bounded convergence policy as the failure boundary, updating
  its convergence condition to include both P and Q plus stability of any
  discrete checks that affect reported compliance.

## Testing Decisions

- Tests assert externally observable `solve_diagram` behavior and returned
  result consistency, not private iteration order or a particular numerical
  algorithm.
- Add legal diagram fixtures for PV-only, BESS-only, hybrid with both fleets,
  and hybrid with a zero/absent secondary fleet. Assert active delivery,
  reactive delivery, apparent power, and effective POC PF against the requested
  combined requirement within explicit tolerances.
- Include the known 3 MW, 0.95 PF regression shape (or an equivalent valid
  diagram) and assert the reactive shortfall is eliminated.
- Include a threshold-crossing diagram where refinement changes a cable's
  current/utilization or loss result. Assert the final selection/check reflects
  converged flow rather than the initial Stage-1 flow.
- Assert station loading/current, circuit current, cable utilization/loss,
  fleet loading, export equipment, loss totals, and power-balance flags are
  internally consistent with the returned final detail rows.
- Assert hybrid reactive attribution is pro-rata by active power and that no
  assertion requires each fleet independently to meet the POC PF.
- Assert a forced cable or other capacity failure after refinement returns the
  existing structured engine-error issue and `results` is null.
- Assert bounded non-convergence returns a structured issue and no partial
  result; do not rely on uncaught exceptions.
- Assert backward-compatible diagram payloads and API response shape, including
  single-fleet diagrams and unknown cosmetic properties. Existing graph
  validation behavior remains covered separately and is not broadened here.
- Run the focused diagram-solve tests first, then the full Python suite and the
  existing frontend typecheck/test/lint commands using isolated test database
  configuration. Numerical tolerances should be tight enough to catch the
  reported defect without depending on binary floating-point identity.

## Out of Scope

- The MV-hybrid multi-edge topology defect.
- PCS capability constraints or any new inverter/PCS operating envelope.
- Catalogue expansion, catalogue-data correction, cable installation factors,
  or electrical standards-factor changes.
- SLD export or report redesign.
- Degradation, augmentation, charging direction, round-trip efficiency, or
  time-series BESS behavior.
- Any change to ambient-rating lookup or transformer catalogue semantics.
- Any change to the declared technology model, graph schema version, or API
  contract unrelated to converged result correctness.
- Frontend visual redesign; only compatibility fixes required to consume the
  corrected existing result meanings are allowed.
- Making each fleet independently meet the POC power factor.

## Further Notes

The audit evidence indicates that the defect is not confined to one displayed
number: refinement currently stops on branch active delivery, while selections,
loading/current checks, loss rows, and result mapping are constructed earlier.
The implementation should therefore be judged by whole-result consistency at
the solve seam, with the 3 MW PF case and threshold-crossing cases acting as
regression anchors.

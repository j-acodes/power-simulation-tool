# 03: Correct hybrid P/Q convergence

**What to build:** Make a hybrid diagram solve each fleet to its own active-power
target while the combined plant satisfies the one physical POC reactive
requirement. Preserve pro-rata reactive attribution and return a complete,
internally consistent result at the converged operating point.

**Blocked by:** 02: Correct single-fleet P/Q convergence

**Status:** done (89b80e8)

- [x] Each active PV and BESS fleet meets its own active-power target at the
      POC; neither fleet can conceal a shortfall in the other.
- [x] Combined delivered P and Q satisfy the requested POC power factor within
      explicit numerical tolerances.
- [x] Reactive duty is attributed pro-rata by fleet active power, and no
      independent per-fleet POC power-factor requirement is introduced.
- [x] For an HV interconnection, the one shared MV/HV transformer and export
      cable are selected and evaluated using combined converged flow.
- [x] Each fleet retains its own busbar, circuits, station loading, cable flow,
      loss details, and compliance decisions, all evaluated at the converged
      operating point.
- [x] A zero-target or absent secondary fleet reproduces the corresponding
      single-fleet result without perturbing shared losses or auxiliary demand.
- [x] Hybrid threshold crossings, discrete selection changes, and bounded
      convergence failures return stable results or structured issues with no
      partial result.
- [x] Summary, fleet, node, edge, and loss details reconcile with one another
      through the diagram-solve interface.
- [x] The existing hybrid topology, diagram/API contracts, positional mapping,
      and accepted ADR decisions remain unchanged, and focused plus full
      verification suites pass.

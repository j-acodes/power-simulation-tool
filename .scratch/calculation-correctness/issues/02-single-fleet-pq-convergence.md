# 02: Correct single-fleet P/Q convergence

**What to build:** Make PV-only and BESS-only diagram solves converge on both
the requested active power and the reactive duty implied by the requested POC
power factor. Every returned quantity and compliance decision must describe
that converged operating point.

**Blocked by:** 01: Introduce recomputable operating-point sizing

**Status:** ready-for-agent

- [ ] A valid PV-only diagram meets its active-power target and requested POC
      reactive duty within explicit numerical tolerances.
- [ ] A valid BESS-only diagram meets the same active/reactive requirements
      without changing container, delivered-energy, duration, or auxiliary-load
      semantics.
- [ ] The known 3 MW at 0.95 power-factor regression no longer returns the
      previously understated reactive delivery.
- [ ] P, Q, apparent power, effective power factor, station loading/current,
      circuit current, cable utilization/loss, fleet loading, export values,
      loss totals, and power balance all come from the converged state.
- [ ] Auto-selected cables are reselected until stable when convergence changes
      their required capacity; forced choices that become invalid return a
      structured engine issue with no partial result.
- [ ] A case that crosses a current, loading, utilization, or loss threshold
      only after refinement is classified using the converged value.
- [ ] Convergence is bounded and deterministic; failure returns the existing
      issue/results envelope rather than an uncaught exception or stale result.
- [ ] Existing single-fleet diagrams and API contracts remain backward
      compatible, and focused diagram-solve plus full verification suites pass.


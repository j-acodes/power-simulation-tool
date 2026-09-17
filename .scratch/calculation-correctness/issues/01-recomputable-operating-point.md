# 01: Introduce recomputable operating-point sizing

**What to build:** Add a behavior-preserving sizing path that can recompute a
complete plant result from a supplied operating point. It must produce the same
station, circuit, cable, fleet, loss, export, and mapped diagram results as the
current path before any convergence behavior changes.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A valid single-fleet diagram can be recomputed from its operating point
      without changing any externally observable solve result.
- [ ] A valid hybrid diagram can be recomputed without changing its shared
      export topology, fleet attribution, node/edge mapping, or solve result.
- [ ] Recomputed results include station P/Q/S and loading, circuit and cable
      flow/utilization/losses, fleet totals, export equipment, and power balance
      as one internally consistent result rather than a mixture of passes.
- [ ] The existing diagram schema, solve response envelope, result field names,
      issue behavior, auxiliary-load semantics, and ambient-rating behavior are
      unchanged.
- [ ] Parity is verified primarily through complete diagram solves; lower-level
      tests are used only where a numerical case cannot be expressed as a valid
      diagram.
- [ ] The full existing Python and frontend verification suites remain green.


# 16: Efficiency run from a design

**What to build:** The modeller points the run at a design's diagram instead of typing the
configuration. The design supplies the BESS solution, station transformers, station and
container counts across the whole BESS fleet, and the POC capacity. The loss chain is the
design's own: station transformers (load and no-load, catalogue figures against the 40 °C
rating), collection cables, HV transformer and export cable, reusing the engine's existing
loss calculation in both directions. Auxiliary consumption is drawn at the MV busbar, so it
carries HV transformer and export cable losses only. In a hybrid, PV is at zero and shared
equipment counts in full. The idle figure uses the design's station and HV transformer no-load
losses. See [spec](../spec.md) and [ticket 03](03-loss-chain.md).

**Blocked by:** 13, 14

**Status:** ready-for-agent

- [ ] A seeded BESS-only design runs, and its station count, solution and POC capacity match
      the design.
- [ ] A hybrid design runs with PV at zero; its HV transformer no-load counts in full.
- [ ] A design with no BESS fleet, or a configuration that conflicts with the design's
      solution, is an error.
- [ ] Charge and discharge losses agree with the engine's forward calculation for the same
      power (same kW loss function, different base).

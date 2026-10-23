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

**Status:** done

- [x] A seeded BESS-only design runs, and its station count, solution and POC capacity match
      the design.
- [x] A hybrid design runs with PV at zero; its HV transformer no-load counts in full.
- [x] A design with no BESS fleet, or a configuration that conflicts with the design's
      solution, is an error.
- [x] Charge and discharge losses agree with the engine's forward calculation for the same
      power (same kW loss function, different base).

## Comments

- 2026-10-23, implementation notes (coordinator): the plant solve moved from the backend into
  the engine (`powertool.plant`, re-exported by the backend) so the run can solve a design
  without crossing the engine boundary. Divergences accepted at merge: the "POC capacity below
  rated active power" check applies to typed runs only (4 h seeds land almost exactly at the
  POC); charge-leg losses are evaluated at each element's container-side power (differs from
  an inward walk by the loss on the loss, under 2 % of chain loss); in a hybrid the PV station
  transformers are excluded and the POC capacity is the BESS fleet's own target; a design
  mixing BESS solutions is an error. A 132 kV export cable is unsized (no catalogue entry), so
  it counts as zero loss.

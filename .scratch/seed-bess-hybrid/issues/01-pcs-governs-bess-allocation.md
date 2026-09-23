# 01: PCS governs BESS allocation; container count capped at the pairing

**What to build:** A drawn BESS or hybrid design shares its BESS duty between stations in
proportion to each station's installed PCS apparent power (containers × PCS units per container ×
PCS kVA), not its transformer-station rating (ADR-0008, mirroring ADR-0005 for PV). PCS active and
apparent limits are checked at 100% of installed PCS as independent warnings that keep results.
The transformer station is still checked separately against its AC power at ambient and the BESS
maximum-loading limit. A container override above the pairing count for the station's chosen
solution is an error-severity validation issue; the canvas container input is capped at that
maximum.

**Key interfaces:**
- `arrange_plant_manual(..., allocation_capacities_kw: list[list[float | None]] | None)` already
  shares duty by per-station capacity. The diagram solve passes installed inverter power for PV
  branches and `None` for BESS; pass installed PCS for BESS:
  `containers * solution.pcs_count * solution.pcs_s_kva` (kVA used as kW, PF-1 reading per ADR-0005).
- Container count comes from `_bess_container_count(props, db, solution)`; the pairing maximum is
  `db.bess_pairings[transformer_key][solution_key]`.
- PV warnings to mirror: `inverter_active_capacity_exceeded` / `inverter_apparent_capacity_exceeded`
  in result mapping (`station.p_lv_kw` / `station.s_lv_kva` vs capacity, 1e-9 tolerance). Add
  `pcs_active_capacity_exceeded` / `pcs_apparent_capacity_exceeded` with the same severity.
- Validation: `_check_props` already rejects a non-positive `containers_override` as `bad_props`;
  add an error-severity issue `containers_above_pairing` when it exceeds the pairing maximum.
- Frontend: the station inspector caps the PV inverter count at `selectedPvPairing.maximum_count`
  with `Math.min`; cap `containers_override` at the paired container count the same way.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Two BESS stations with different container counts receive P/Q shares proportional to installed PCS
- [ ] A full MVS7400-LS + ST6900UX-4H station is allocated on 4 × PCS kVA × PCS units, not 7400 kVA
- [ ] PCS active and apparent over-limit each produce a warning; results are still returned
- [ ] Transformer-station loading still uses allocated duty and the BESS maximum-loading limit
- [ ] A container override above the pairing count is an error on that station; equal to it validates
- [ ] A hybrid with zero BESS power still reproduces PV-only exactly
- [ ] PV behaviour is unchanged
- [ ] The canvas container-count input cannot exceed the pairing maximum
- [ ] Focused tests pass at the diagram-solve seam; Python and TypeScript type checks pass
- [ ] Golden baseline differences are limited to BESS/hybrid cases and listed in the report (baseline refresh itself is ticket 04)

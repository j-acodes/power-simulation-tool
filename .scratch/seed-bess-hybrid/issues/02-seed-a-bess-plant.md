# 02: Seed a BESS plant

**What to build:** On a design whose declared technology is BESS, the seed wizard shows only BESS
inputs: point-of-connection BESS power, discharge duration, then a BESS solution that sells that
duration, then a station model paired with that solution, plus maximum loading, trunk length and
spacing alongside the shared fields (interconnection, voltages, power-factor target, export
length, auxiliary load, feeders per busbar). The seed sizes the station count to power using
installed PCS at the pairing maximum, then sizes containers to power × duration: stations are
filled to the pairing maximum in circuit order with the remainder on the last; if full stations
fall short, stations are added until energy is met. The proposed diagram carries the duration as
its discharge duration setting, the BESS power on the point of connection, the BESS maximum-loading
rule, a BESS busbar with the auxiliary load, and `bess` stations. PV-design seeding is unchanged.

**Key interfaces:**
- `seed_diagram(params: dict, db) -> dict` fixed-points a PV station count via
  `_stage1_for_count` + `size_generation`, then `arrange_plant(...)` and `_layout_to_diagram`.
  Branch on `params["technology"]`; the PV path must stay byte-for-byte as today.
- `SeedRequest` (Pydantic, `POST /api/seed`) gains `technology: Technology` (default `"pv"`) and an
  optional BESS block: `p_poc_bess_mw`, `discharge_hours`, `bess_solution`, `bess_station_model`,
  `max_loading_bess`, `trunk_bess_m`, `spacing_bess_m` (names are a suggestion; mirror them in
  frontend `SeedParams`). PV fields become optional, required by a model validator only when the
  technology permits PV; BESS fields likewise. Reject: solution whose `duration_h` ≠
  `discharge_hours`; station not in `db.bess_pairings` for that solution.
- Catalogue: `db.bess_solutions[key]` (`e_nominal_kwh` per container, `pcs_count`, `pcs_s_kva`,
  `duration_h`); `db.bess_transformers[key]`; pairing maximum
  `db.bess_pairings[station_key][solution_key]`. Per-station installed PCS at the maximum =
  `max × pcs_count × pcs_s_kva` (kVA read as kW, ADR-0008) — the BESS analogue of
  `per_station_capacity`.
- Containers: required = `ceil(p_bess_kw × discharge_hours / e_nominal_kwh)`; the engine's
  energy check is exactly `Σ containers × e_nominal_kwh ≥ p_target_bess_kw × discharge_hours`.
- Diagram output: POC `p_target_mw` carries the BESS power (a single-fleet design reads its
  target there; `p_target_bess_mw` is only the second fleet's figure in a hybrid); rules `discharge_hours`,
  `max_loading_bess`; busbar and stations `fleet_kind: "bess"`; station props `model` (BESS
  transformer key), `bess_solution`, `containers_override` only where below the maximum. Read how
  drawn BESS stations are shaped in the hybrid tests' `_hybrid_with_drawn_bess()` helper.
- Frontend: `SeedWizard` reads `designMeta.technology` from the store; catalogue gives
  `bess_solutions` (`BessSolutionInfo.duration_h`) and `bess_transformers`
  (`TransformerInfo.paired_solutions: Record<solutionKey, maxContainers>`).

**Blocked by:** 01: PCS governs BESS allocation; container count capped at the pairing.

**Status:** done

- [x] Seed request accepts a technology and a BESS block; PV fields are required only when PV is permitted
- [x] Request rejects a solution that does not sell the duration and a station not paired with the solution
- [x] Container fill: stations at the maximum in order, remainder on the last, override written only where below the maximum
- [x] Energy shortfall at the maximum adds stations until energy is met
- [x] Seeded BESS diagram validates and solves with energy met and loading within the limit
- [x] Seeding is deterministic
- [x] Wizard on a BESS design shows only BESS inputs; selectors cascade duration → solution → station
- [x] Wizard on a PV design is unchanged; existing PV seed tests pass untouched
- [x] Focused seed tests, wizard test and type checks pass

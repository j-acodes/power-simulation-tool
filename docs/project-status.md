# Project status

This status is checked against the repository code and accepted ADRs. Three historical
implementation plans supplied during the handoff are context only and are superseded by
code, specs, and ADRs: the interactive builder plan, the separate PV/BESS and hybrid plan,
and the BESS component-datasheets plan describe how the current shape was reached. They are
not a second source of requirements.

## Implemented

- The Python engine models component catalogues, loss-cascade sizing, cable auto-sizing,
  per-fleet hybrid architecture, and result mapping (`powertool/`).
- The FastAPI app exposes catalogue, stage-1 and diagram solve, PDF report, project/design
  CRUD, seed, and optimistic-locking save routes (`backend/main.py`, `backend/solve.py`).
- React/TypeScript provides the project/design editor, React Flow diagram, Zustand state,
  palette and inspector, catalogue/specification views, result tables, seed flow, and PDF
  download (`frontend/src/`).
- PV, BESS, and hybrid designs are represented with one POC, shared export equipment, and
  one busbar/cascade per fleet. Technology is declared at design creation and changed by
  cloning; these are accepted decisions in [ADR-0001](adr/0001-hybrid-pv-bess-topology.md)
  and [ADR-0002](adr/0002-technology-declared-not-derived.md).
- YAML catalogues include PV and BESS transformer stations, cables, datasheet-backed BESS
  solutions, and Sungrow/Huawei PV inverters. Supported PV transformer stations declare their
  inverter pairings and a maximum count; every PV station must carry one paired inverter and a
  whole-number count. A station is deployed with its paired inverter at that maximum, on the
  palette, in the seed wizard and on a model change, and the inverter is presented as a choice
  only where a station declares more than one pairing. One click applies a model to every
  catalogue PV station, refilling each one's inverter and count. TBEA stations are no longer
  selectable.
- PV conversion duty is allocated by installed inverter power at the selected ambient and is
  checked independently for active power, apparent power, and published minimum power factor.
  Transformer-station loading remains a separate check. Ambient lookup and provenance follow
  [ADR-0004](adr/0004-ac-power-per-ambient-temperature.md) and
  [ADR-0005](adr/0005-inverter-power-governs-pv-conversion.md).
- The seed wizard proposes a BESS or hybrid plant from the design's declared technology, not
  only PV. A BESS design sizes station count to point-of-connection BESS power at the pairing
  maximum, then sizes container counts to power × discharge duration — filling stations to the
  maximum in circuit order, remainder on the last, adding stations if the maximum still falls
  short on energy — and writes the chosen duration into the design. A hybrid design seeds both
  fleets from one wizard, PV left and BESS right of a centred point of connection, each with its
  own trunk length, spacing, and maximum-loading limit. BESS duty is allocated between stations
  by installed PCS apparent power rather than transformer-station rating, mirroring ADR-0005's
  PV rule; PCS active- and apparent-power limits are checked independently as warnings (not
  errors) at 100% of installed PCS, with no ambient lookup, while the transformer station is
  still checked separately against its own AC power at ambient and the BESS maximum-loading
  limit. A station's container count above its solution's pairing maximum is a validation error,
  and the canvas container-count input is capped at that maximum. See
  [ADR-0008](adr/0008-pcs-governs-bess-conversion-and-containers-are-sized.md).
- Catalogue, setup, and station-inspector views expose separate full specifications for PV
  transformer stations and inverters, with simulated parameters, typed supplier facts,
  pairings, missing-data notices, and source provenance. Inverters remain contained products,
  not draggable canvas nodes.

## Deferred and operational gaps

- BESS round-trip efficiency, charging direction, time-series behaviour, and OND/datasheet
  parsing remain outside the implemented sizing path; the current model is steady-state and
  treats BESS discharge as generation.
- There is no authenticated shared/company deployment setup. SQLite and wholesale schema
  creation remain appropriate for the current single-engineer setup; there is no Alembic
  migration path, checked-in CI, or browser E2E suite.
- Saved-design import/export and automated database backup are not provided. PDF export is
  implemented, while the local SQLite file remains runtime state rather than a portable
  project archive.
- Existing diagrams that omit a PV inverter selection and count are intentionally invalid;
  there is no synthetic legacy inverter or payload migration path.

## Architecture and decisions

`powertool/` owns physics and sizing. `backend/` translates diagram JSON to the engine,
serves the API, and persists opaque diagrams. `frontend/` renders and edits the API's
contracts. `data/*.yaml` is the editable component source; catalogue data is loaded at
startup rather than stored in SQLite.

The branch proposal `docs/adr-postgres-deferred:docs/adr/0003-sqlite-until-deployment.md`
records a possible future move to Postgres bundled with Alembic. It is not merged and is not
an accepted main-branch decision. Its trigger is deployment to a shared company server;
until then, preserve the current SQLite/reset workflow and require explicit authorization for
any reset.

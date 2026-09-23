# 04: Cutover, baseline and docs

**What to build:** The golden baseline is refreshed for the BESS/hybrid numbers that ADR-0008
shifts, with each changed case explained. The CTO-Demo rebuild script still produces a valid,
solving project. Project status documentation records BESS and hybrid seeding and PCS-governed
allocation. A database reset, if needed, happens only with the owner's explicit authorization.

**Blocked by:** 03: Seed a hybrid plant.

**Status:** ready-for-agent

- [ ] Golden baseline refreshed; only BESS/hybrid cases differ, each difference explained
- [ ] CTO-Demo rebuild script runs against a disposable database and the project solves
- [ ] Project status documentation updated
- [ ] Full Python and frontend test suites and type checks pass
- [ ] One real-browser check per technology (PV, BESS, hybrid) seeding from the wizard

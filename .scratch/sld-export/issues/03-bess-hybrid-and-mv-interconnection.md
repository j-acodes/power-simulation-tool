# 03: BESS stations, several busbars, hybrid and MV interconnection

**What to build:** the SLD covers every topology the tool solves. One sheet per busbar, each
showing its busbar, circuits and stations plus the chain up to the POC. BESS stations draw one
PCS symbol "× N model" and a battery symbol labelled with its MWh. A hybrid plant's shared HV
transformer and POC repeat at the top of both sheets. An MV interconnection draws POC →
metering → breaker → export cable → busbar with no HV transformer. TS, C and BB numbering is
plant-wide in order busbar → circuit → position.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Layout-model tests: a fleet with several busbars gives one sheet per busbar with plant-wide tags continuing across sheets; a hybrid gives a PV and a BESS sheet both carrying the shared POC and HV transformer; an MV interconnection has no HV transformer element
- [ ] BESS station labels: PCS "× N model key" and battery MWh
- [ ] Browser check on a hybrid design: downloaded SLD opened, both sheets screenshot and reported
- [ ] `tests/golden_baseline.json` byte-identical; full pytest, Vitest, build and lint pass

# 04: Drawing-only auxiliary transformer

**What to build:** each auxiliary load appears on its busbar sheet as its own feeder with a
breaker, an auxiliary transformer tagged AUX1… (plant-wide), and a load symbol labelled with its
kW. The transformer rating is the smallest of 50, 100, 160, 250, 315, 400, 500, 630, 800, 1000,
1250, 1600, 2000, 2500 kVA at or above S_aux / 0.80 (S from the load's P and Q), LV 0.4 kV.
An unpublished auxiliary figure gives "kVA TBD†"; above 2500 kVA gives "> 2500 kVA†"; both are
listed in the † notes. A sheet note says the auxiliary transformer is sized for the drawing only
and is not in the loss calculation. The calculation does not change.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] Rating-selection tests: exact boundary (S/0.8 equal to a standard rating picks that rating), just above picks the next, Q contributes to S, unpublished gives TBD†, above range gives > 2500 kVA†
- [ ] Layout-model test: a BESS busbar with an auxiliary load has an AUX element on its own feeder with breaker and load label; a busbar without one has none; the drawing-only note is present only when an AUX element is
- [ ] `tests/golden_baseline.json` byte-identical (proves the calculation is untouched); full pytest, Vitest, build and lint pass
- [ ] Browser check on a BESS design with auxiliaries: downloaded SLD opened and screenshot reported

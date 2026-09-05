# 01: Reshape the BESS solution around a declared discharge duration

**What to build:** A sizing engineer opens a BESS design and picks a real product — Sungrow's
PowerTitan 3.0 ST6900UX-4H — identified by the brand, series and model number printed on the
supplier's own datasheet. The invented placeholder solutions are gone.

A BESS solution no longer carries a table of container counts against discharge durations. It
declares **one** discharge duration, because the supplier's model number already encodes it and
that is what gets procured. Sungrow's 6904 kWh across four 450 kVA units computes to 3.84 h and
the nameplate still says 4H: **discharge duration is declared, not derived**, in the same sense
ADR-0002 makes technology declared rather than derived.

PCS rating is stored the way the datasheet states it — apparent power per PCS plus a unit count —
rather than as a single active-power figure. Confirm before renaming that no part of the engine
consumes PCS rating (at time of writing only container energy is consumed), and do not introduce
a consumer of it in this ticket.

The catalogue key becomes a slug of brand and model. The display name leads with the series and
qualifies it with the model number, because the series is how the product is recognised and the
model number is what separates two durations of it.

Every existing saved design names a deleted solution and will fail validation with the existing
unknown-solution error. That is the intended outcome: the database is reset rather than migrated.
**This destroys every project and design and is not reversible.**

The BESS module's golden snapshot pins numbers this change moves. Regenerate it deliberately and
read the diff; do not regenerate it blindly.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A BESS solution declares a single discharge duration; the per-solution duration table no
      longer exists anywhere in the model, the catalogue payload, the frontend types or the YAML
- [ ] A BESS solution carries brand, series and model number, and is keyed by a slug of brand
      and model
- [ ] The display name leads with the series and qualifies it with the model number
- [ ] PCS rating is stored as apparent power per unit plus a unit count, and nothing in the
      engine reads either
- [ ] The Sungrow ST6900UX-4H entry is present with its published DC, AC and system parameters;
      no entry in the catalogue is flagged as placeholder data
- [ ] The auxiliary figures are zero for Sungrow, because the datasheet publishes none
- [ ] The catalogue endpoint serves the reshaped solution and the frontend types match it
- [ ] The existing discharge-duration control still works, sourced from the new shape
- [ ] A design naming a deleted solution fails validation with the existing unknown-solution
      error rather than crashing
- [ ] The database has been reset and the application starts clean
- [ ] The golden snapshot is regenerated and its diff is explained in the commit

# 08: Reporting

**What to build:** The PDF stands alone in a design review for a battery or hybrid project.

The report gains what a BESS design needs to be assessed without the tool open: container
counts, delivered energy against required energy, and per-fleet loading. In a hybrid report,
the two fleets are presented distinctly rather than merged into one station table.

The conversion device is **labelled** per station kind — "PCS" on battery stations, "inverter"
on PV. The underlying result fields are not renamed or duplicated; only the presentation
differs. This holds in the PDF and in the results tables alike.

**Blocked by:** 07 (BESS sizing and compliance)

**Status:** ready-for-agent

- [ ] The report includes container counts and the energy compliance outcome for BESS fleets
- [ ] Per-fleet loading appears for each fleet in a hybrid report
- [ ] Conversion-level figures are labelled "PCS" for BESS stations and "inverter" for PV
      stations, in both the PDF and the results tables
- [ ] The two fleets of a hybrid design are presented distinctly
- [ ] A PV-only report is unchanged apart from the neutral naming introduced in ticket 01
- [ ] Python suite, frontend typecheck, tests and lint all pass

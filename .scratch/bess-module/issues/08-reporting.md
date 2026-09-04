# 08: Reporting

**What to build:** The PDF stands alone in a design review for a battery or hybrid project.

The report gains what a BESS design needs to be assessed without the tool open: container
counts, delivered energy against required energy, and per-fleet loading. In a hybrid report,
the two fleets are presented distinctly rather than merged into one station table.

The conversion device is **labelled** per station kind — "PCS" on battery stations, "inverter"
on PV. The underlying result fields are not renamed or duplicated; only the presentation
differs. This holds in the PDF and in the results tables alike.

**Blocked by:** 07 (BESS sizing and compliance)

**Status:** done (761ddfd)

- [x] The report includes container counts and the energy compliance outcome for BESS fleets
- [x] Per-fleet loading appears for each fleet in a hybrid report
- [x] Conversion-level figures are labelled "PCS" for BESS stations and "inverter" for PV
      stations, in both the PDF and the results tables
- [x] The two fleets of a hybrid design are presented distinctly
- [x] A PV-only report is unchanged apart from the neutral naming introduced in ticket 01
- [x] Python suite, frontend typecheck, tests and lint all pass

## Review findings acted on (2026-09-04)

Both defects were in the same criterion — *"A PV-only report is unchanged apart from the
neutral naming introduced in ticket 01"* — and neither was caught by the test suite.

1. The first per-fleet restructure split Stage 2 into a plant table plus a fleet table and
   annotated the loading with its maximum. A PV-only report genuinely changed. With one
   fleet the plant IS the fleet, so its figures and the plant totals now stay in ONE table
   in their original order, and the maximum is a hybrid-only annotation.
2. The `(shared)` note on the MV/HV transformer and export rows went out unconditionally.
   A PV-only **HV** plant therefore read "(MV/HV, shared)" about a step nothing shares,
   and `Export (shared)` no longer fitted the 0.8-wide Run column, wrapping to three lines
   and visually detaching the row's figures from their label. The fixture the first check
   used (`_minimal()`) is MV-interconnected and has no export rows at all — which is
   exactly why it was missed. Both fixtures are exercised now.

Verification that actually settles this criterion: render the report at HEAD and after,
and diff the extracted text.

    git worktree add --detach /tmp/pristine HEAD
    # render /api/report for _minimal() AND _hv_diagram() from both trees
    pdftotext -layout before.pdf before.txt && pdftotext -layout after.pdf after.txt
    diff <(tail -n +3 before.txt) <(tail -n +3 after.txt)    # skip the timestamp line

Both shapes came back identical. The suite cannot see this property, so
`tests/test_pdf_report.py` pins what made it true: one Stage-2 table for a single fleet,
no "max" annotation, and no "shared" anywhere a single fleet can reach.

Also fixed: `ResultsSummary` still hard-coded "Inverters" while the tables one click away
said "Required PCS units"; `_fleet_prefix` returned a string shaped for a row label that
the heading call site had to reverse-parse with `rstrip("— ")`, now `_fleet_name` returning
the bare name; `fleet_label` added beside `conversion_label` so the Python side mirrors the
frontend's `fleetLabel`/`conversionLabel` pair.

## Open question, not in scope here

Loss percentages in a hybrid are quoted against the PLANT's total refined conversion power,
so the two fleets' columns share one base and can be read against each other. A fleet's
"ΔP % of P_inv" is therefore not its share of its own power. Defensible either way; raised
with the owner, unanswered.

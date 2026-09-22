# SLD export

**Status:** ready-for-agent

## Problem Statement

The engineer draws the plant as an aggregate diagram (one station block per fleet) and the tool
sizes it into busbars, circuits and individual stations. The only way to take that result out of
the tool is the PDF sizing report, which is tables. There is no drawing of the plant as it would
be built, so anyone who needs a single-line diagram (SLD) — a client, a reviewer, a drafter
starting the real drawings — has to redraw it by hand from the report tables.

## Solution

A **Download SLD** action next to the existing report download produces an IEC-style
single-line diagram of the *solved* design as a standalone A3-landscape PDF, one sheet per
busbar. The same sheets also appear, scaled down, inside the PDF sizing report. The drawing is
generated from the sizing result, not from the canvas: every circuit and every station the tool
sized is drawn, laid out automatically, with IEC 60617-style symbols, equipment tags, and the
sized figures printed beside each symbol. It is explicitly preliminary: indicative protection
devices, a drawing-only auxiliary transformer, and a "PRELIMINARY — NOT FOR CONSTRUCTION" stamp.

## User Stories

1. As a design engineer, I want a Download SLD button next to the report button, so that I can get a drawing of the design without redrawing it.
2. As a design engineer, I want the SLD to reflect what is on the canvas right now, including unsaved changes, so that it matches what I am looking at, the same way the report does.
3. As a design engineer, I want the SLD download to refuse with the reason when the design does not solve, so that I never get a drawing of a design the tool could not size.
4. As a design engineer, I want every circuit and every station the tool sized drawn individually, so that the drawing shows the plant as it would be built rather than the aggregate blocks.
5. As a design engineer, I want one A3 landscape sheet per busbar, so that each sheet stays readable at any plant size.
6. As a design engineer, I want every busbar sheet to also show the chain from that busbar up to the point of connection, so that each sheet reads on its own.
7. As a design engineer with a hybrid plant, I want the shared HV transformer and point of connection shown at the top of both the PV and the BESS busbar sheets, so that each sheet is complete.
8. As a design engineer with an MV interconnection, I want the chain drawn without an HV transformer, so that the drawing matches the topology I designed.
9. As a design engineer, I want the busbar drawn horizontally with each circuit hanging down from it as a column of stations in chain order, so that the layout follows SLD convention and the daisy chain is obvious.
10. As a reviewer, I want IEC 60617-style symbols (transformer, circuit breaker, load-break switch, disconnector, busbar, cable, inverter, battery, load), so that the drawing reads like any other SLD.
11. As a reviewer, I want indicative protection devices drawn — breakers on feeders, export and grid side; load-break switches in station switchgear; disconnector and metering at the point of connection — so that the drawing reads as an SLD even though the tool does not size those devices.
12. As a reviewer, I want a note on each sheet stating that protection devices are indicative, so that no one mistakes them for sized equipment.
13. As a reviewer, I want a symbol legend on every sheet, so that I can read the drawing without a separate key.
14. As anyone referring to equipment, I want stations tagged TS1, TS2… numbered across the whole plant in order busbar → circuit → position from the busbar, so that every station has a unique name across all sheets.
15. As anyone referring to equipment, I want circuits tagged C1, C2…, busbars BB1, BB2… and auxiliary transformers AUX1, AUX2…, so that I can say "TS3 on C2".
16. As a reviewer, I want the point of connection labelled with its voltage and MW, so that the grid-side requirement is on the drawing.
17. As a reviewer, I want the HV transformer labelled with its model and MVA, so that the main transformer is identified.
18. As a reviewer, I want each busbar labelled with its voltage, so that the collection level is clear.
19. As a reviewer, I want each circuit's feeder labelled with its switchgear rated current, so that the feeder rating is visible.
20. As a reviewer, I want every cable segment — export spans and each circuit segment — labelled with its size, material, parallel-run count and length, so that tapered circuits and parallel runs are visible.
21. As a reviewer, I want each station labelled with its transformer model and kVA, so that the conversion equipment is identified.
22. As a reviewer, I want each PV station's LV side drawn as one inverter symbol labelled "× N model", so that the inverter composition is visible without drawing N inverters.
23. As a reviewer, I want each BESS station's LV side drawn as one PCS symbol labelled "× N model" and a battery symbol labelled with its MWh, so that the storage composition is visible.
24. As a reviewer, I want no DC capacity on PV stations, no losses and no loading percentages on the drawing, so that the drawing stays uncluttered and those figures stay in the report tables.
25. As a reviewer, I want model names on the drawing to be the catalogue model keys, so that the drawing matches what the editor and catalogue show.
26. As a BESS designer, I want each auxiliary load drawn as an auxiliary transformer on its own busbar feeder with a breaker, then a load symbol labelled with its kW, so that the auxiliary supply appears on the SLD.
27. As a BESS designer, I want the auxiliary transformer rating chosen automatically as the smallest standard rating at or above the auxiliary apparent power ÷ 0.80, LV 0.4 kV, so that it has a sensible size without my input.
28. As a BESS designer whose supplier publishes no auxiliary figure, I want the auxiliary transformer drawn with "kVA TBD†", so that the drawing shows equipment that will exist without inventing a rating.
29. As a reviewer, I want a note stating that the auxiliary transformer is sized for the drawing only and is not part of the loss calculation, so that no one thinks the figures include it.
30. As a reviewer, I want any value that came from a fallback (for example the 630 A switchgear rated current) marked † and listed in a note on the sheet, so that assumed values are never presented as datasheet values.
31. As a design engineer, I want a title block with project name, design name, date and "Generated by Power Simulation Tool", so that a printed sheet identifies itself.
32. As anyone receiving the drawing, I want a "PRELIMINARY — NOT FOR CONSTRUCTION" stamp on every sheet, so that it cannot be mistaken for issued drawings.
33. As a design engineer, I want a busbar sheet that does not fit A3 to scale down, and to split across continuation sheets with "continued" markers only once text would fall below 5 pt, so that large plants stay legible.
34. As a design engineer, I want the file named `<design>-sld.pdf`, so that it sits next to the sizing report sensibly.
35. As a report reader, I want each busbar sheet embedded in the sizing report after the summary, scaled to the page width, with a caption pointing to the standalone SLD download, so that the report shows the plant and says where to find the legible version.
36. As a design engineer, I want the drawing to stay vector (sharp when zoomed) in both the standalone PDF and the report, so that small text on large plants can still be read by zooming.

## Implementation Decisions

- **One new engine module, the SLD builder**, lives in the engine package beside the PDF report
  and, like it, stays independent of the diagram layer. It takes the solved plant architecture
  plus the per-fleet reporting records (the same `branches_summary` dicts the report receives)
  and the fallback-notice data, and produces sheets.
- **Two layers inside the module:**
  1. A pure **layout model**: `sld_sheets(arch, fleets, …) -> list[Sheet]`. A `Sheet` is plain
     data — the busbar tag, the sheet's elements (symbol kind, tag, position, label lines), the
     connections between them, the † notes, the legend entries, the continuation marker and the
     scale. All the decisions (tagging, ordering, label text, auxiliary transformer rating,
     † marking, scale and split) are made here.
  2. A thin **renderer** turning a `Sheet` into a ReportLab `Drawing` (vector graphics). ReportLab
     is already a dependency; no new library.
- **Standalone PDF:** `build_sld_pdf(...) -> bytes` renders one A3-landscape page per sheet, each
  with frame, title block, stamp, legend and notes.
- **Report embedding:** the report story inserts each sheet's `Drawing`, scaled to the A4 text
  width, after the summary, with a caption naming the standalone download. The Drawing stays
  vector; "image" means a scaled picture of the sheet, not a raster.
- **Backend:** a new `POST /api/sld?name=` endpoint mirrors `POST /api/report`: same body (the
  diagram payload), same validation-then-solve pipeline, 400 with the first issue's message
  when the design does not solve, `application/pdf` with
  `Content-Disposition: attachment; filename="<slug>-sld.pdf"` using the existing filename
  slug. The report pipeline passes the same inputs to the SLD builder for embedding.
- **Frontend:** a **Download SLD** button beside the report button, wired the same way as the
  report download (same API-client pattern, same error surfacing).
- **Layout convention:** point of connection at the top, then the grid-side chain, the busbar
  horizontal across the sheet, circuits as vertical columns hanging from it in circuit order,
  stations stacked in chain order (position 0 nearest the busbar). Auxiliary feeders sit at the
  busbar's end after the circuits. The sheet scale shrinks to fit A3; at the 5 pt text floor the
  busbar's circuits split across continuation sheets, each repeating the busbar and marked
  "continued from / on sheet n".
- **Grid-side chain:** with an HV transformer: POC (voltage, MW) → metering → disconnector →
  HV breaker → HV transformer (model, MVA) → export cable span(s) → MV incomer breaker → busbar.
  MV interconnection: POC → metering → breaker → export cable → busbar. In a hybrid, the shared
  part (POC, HV transformer) repeats on each busbar sheet.
- **Tags:** TS numbering is plant-wide, ordered busbar → circuit → position. C, BB and AUX are
  likewise plant-wide. Cable segments carry no tag.
- **Labels:** exactly the set in stories 16–23 and 26. Model names are catalogue model keys, not
  display labels (the architecture's station `model` field is a display label, so the builder
  must resolve the key).
- **Auxiliary transformer (drawing only):** rating = smallest of 50, 100, 160, 250, 315, 400, 500,
  630, 800, 1000, 1250, 1600, 2000, 2500 kVA that is ≥ S_aux / 0.80, where S_aux comes from the
  auxiliary load's P and Q. LV 0.4 kV. An unpublished auxiliary figure gives "kVA TBD†". Above
  2500 kVA: label the rating "> 2500 kVA†". It never enters the power balance; the golden
  baseline must not change.
- **† notes:** driven by the same fallback data `fallback_notices` already reports, plus the
  auxiliary transformer rules above. Each † value is listed with its reason on the sheet it
  appears on.
- **No schema change, no settings change, no calculation change**, so no database reset.

## Testing Decisions

- A good test asserts on what a reader of the drawing would see — which tags exist, which label
  text sits on which tagged element, which sheet it is on, which notes are listed — never on
  coordinates or drawing primitives.
- **Primary seam: the layout model.** Tests build an architecture through the existing engine
  entry points (as the report tests do) and assert on `sld_sheets(...)`: sheet count per
  busbar, TS/C/BB/AUX tags and ordering, per-segment cable labels, † marks and notes,
  auxiliary transformer rating selection (including the TBD and above-range cases), hybrid and
  MV-interconnection chains, and the continuation split.
- **Rendering smoke:** the standalone PDF is non-empty, A3 landscape, one page per sheet; the
  report story contains one drawing per sheet after the summary. No pixel or PDF-text
  comparison.
- **Endpoint:** `/api/sld` returns a PDF with the right filename for a solvable design and a 400
  with the reason for an unsolvable one, mirroring the existing report endpoint tests.
- **Frontend:** Vitest only if a pure helper is added; the button is checked in a real browser
  (see the project's Playwright visual-check practice) by downloading and opening the PDF.
- **Prior art:** the report's `report_story` tests (content asserted on flowables, not on PDF
  bytes) and the report endpoint tests.
- The full suite, `tests/golden_baseline.json` byte-identical, frontend Vitest, `npm run build`
  and `npm run lint` must pass on every ticket.

## Out of Scope

- Modelling the auxiliary transformer in the calculation (losses, loading, report tables).
- Using TS/C/BB tags in the report tables or the editor.
- DXF or other CAD export; editable drawings.
- Protection device sizing or selection; earthing, metering class, CT/VT details.
- Revision tracking in the title block.
- PV DC capacity, losses or loading on the drawing.
- Changing the canvas layout or the editor's rendering.

## Further Notes

- The layout is generated, not taken from the canvas: the canvas holds the aggregate topology,
  and the SLD shows the expanded plant.
- The auxiliary transformer figures are presented as drawing-only on purpose. If they should
  ever enter the power balance, that is a separate calculation unit that moves the golden
  baseline.

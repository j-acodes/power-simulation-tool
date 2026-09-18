# Spec: PV inverter components and complete PV transformer-station datasheets

Status: ready-for-agent

## Problem Statement

A sizing engineer can select a PV transformer station, but cannot select the inverter product
or say how many inverters sit behind that station. The sizing engine therefore treats the
transformer station's AC power at ambient as the source of PV fleet capacity and distributes
fleet duty between stations by transformer-station rating. That confuses two pieces of
equipment with different responsibilities: the inverter fleet establishes how much active and
reactive power can be converted, while the transformer station carries that operating point
subject to its own loading, loss and voltage characteristics.

PV catalogue entries also lag behind the BESS catalogue contract. They are presented as compact
rows rather than complete supplier products, most of their typed datasheet fields are absent,
their compatible inverters and physical input counts are not represented, and an engineer
cannot open a consistent specification view that distinguishes parameters used by the sizing
engine from parameters transcribed only for review.

The result is a material sizing risk. Two stations with the same transformer-station rating but
different installed inverter capacity are currently treated as equivalent. A design can appear
to have adequate PV conversion capacity without naming any inverter at all, and the catalogue
does not expose enough provenance for that assumption to be defended in a design review.

## Solution

Introduce the **inverter** as a first-class PV catalogue product contained by a **station**. It
is selected and counted inside the station, like containers behind a BESS station, but it is
never an independently drawable node. A PV transformer station declares which inverter products
it is paired with, the maximum physical count for each pairing and the default count. The
engineer may reduce or restore the count within that physical range.

The requested POC active power and power factor remain the operating requirement. The sizing
engine works backward through losses as it does today, but distributes the resulting PV
conversion duty by each station's installed ambient-rated inverter capacity. It checks both
active power and apparent power against that capacity, checks the selected inverter's published
minimum power factor when available, and reports prominent non-blocking warnings when the
operating point exceeds those limits. Transformer loading remains a separate compliance check
against the transformer station's own AC power at ambient.

PV transformer stations and PV inverters adopt the complete catalogue format already established
for BESS: stable product identity, a leading “What the simulation uses” section, grouped typed
datasheet fields, pairing information, source provenance, explicit missing-data notices and a
full read-only specification view reachable from the catalogue and a placed station.

The first supported products are Sungrow PV transformer stations paired with the SG350HX-20 and
Huawei JUPITER-H1 transformer stations paired with the SUN2000-330KTL-H1. TBEA entries are
removed. Existing projects are deliberately not migrated; the authorized implementation reset
permanently deletes all projects and designs from the active default SQLite database without a
backup.

## User Stories

1. As a sizing engineer, I want an inverter to be a named catalogue product, so that my design
   identifies the conversion equipment that will actually be procured.
2. As a sizing engineer, I want the inverter to live inside a station rather than as a canvas
   node, so that the single-line diagram continues to show the accepted aggregate topology.
3. As a sizing engineer, I want to select a PV transformer station before its inverter, so that
   the station product controls which supplier-supported pairings are offered.
4. As a sizing engineer, I want to see only the inverter models paired with the selected PV
   transformer station, so that I cannot choose an unsupported catalogue combination.
5. As a sizing engineer, I want each station to contain one inverter model, so that its installed
   capacity and supplier pairing remain unambiguous.
6. As a sizing engineer, I want to enter an integer inverter count for each station, so that I
   can represent a partially populated transformer station.
7. As a sizing engineer, I want inverter count constrained to the physical range declared by
   the station pairing, so that I cannot populate more inverter inputs than the product provides.
8. As a sizing engineer, I want inverter count to default to the station's maximum physical
   inputs, so that a fully populated station is the fast path.
9. As a sizing engineer, I want setup to calculate the number of PV stations from installed
   inverter capacity, so that generated layouts are not sized from transformer-station rating.
10. As a sizing engineer, I want setup to account for both active and apparent inverter capacity,
    so that a reactive requirement can increase the number of stations needed.
11. As a sizing engineer, I want setup to check transformer loading separately, so that a valid
    inverter arrangement does not conceal an overloaded transformer station.
12. As a sizing engineer, I want to change inverter model and count in a placed station's
    inspector, so that I can refine the generated layout without rebuilding it.
13. As a sizing engineer, I want different stations in one PV fleet to use different inverter
    models or counts, so that mixed layouts can represent real procurement and phasing.
14. As a sizing engineer, I want fleet duty distributed by installed inverter capacity, so that
    a station with more conversion capacity carries a proportionally larger share.
15. As a sizing engineer, I want the POC active-power target to remain the requested operating
    point, so that adding nameplate capacity does not force the plant to export at nameplate.
16. As a sizing engineer, I want the POC power factor to remain the source of reactive duty, so
    that the grid requirement continues to govern the operating point.
17. As a sizing engineer, I want active station duty checked against inverter active capacity,
    so that the design exposes an active-power shortfall.
18. As a sizing engineer, I want apparent station duty checked against inverter apparent
    capacity, so that reactive duty cannot exceed the conversion equipment's capability.
19. As a sizing engineer, I want inverter ratings interpreted at power factor 1, so that active
    and apparent capacity use the same supplier or declared rating at each ambient temperature.
20. As a sizing engineer, I want the inverter-side operating power factor checked against the
    product's minimum power factor, so that a mathematically possible point outside the declared
    adjustment range is still reported.
21. As a sizing engineer, I want an inverter capacity or power-factor violation to return
    calculated results plus a prominent warning, so that I can see the size of the shortfall
    instead of receiving no result.
22. As a sizing engineer, I want transformer-station loading to remain independent of inverter
    capacity, so that the transformer still has its own visible compliance result.
23. As a sizing engineer, I want the existing PV maximum-loading setting to apply only to the
    transformer station, so that it does not silently derate the inverter.
24. As a sizing engineer, I want explicit inverter ratings at 30 °C and 40 °C used without
    interpolation, so that the tool does not invent an ambient curve.
25. As a sizing engineer, I want a missing 30 °C inverter rating to fall back conservatively to
    the 40 °C rating with a notice, so that missing supplier data does not inflate capacity.
26. As a sizing engineer, I want to create a one-off custom station with custom inverter values,
    so that a product absent from the curated catalogue does not block a project.
27. As a sizing engineer, I want a custom inverter to require a name, 40 °C power and count, so
    that every custom station has enough data for the engine to size it.
28. As a sizing engineer, I want custom 30 °C power and minimum power factor to be optional, so
    that unknown supplier values are not invented.
29. As a sizing engineer, I want custom nominal AC voltage recorded but not validated, so that
    compatibility remains an engineering assumption rather than an engine gate.
30. As a sizing engineer, I want catalogue pairings treated as electrically compatible without
    a separate voltage-match validation, so that the declared supplier pairing is authoritative.
31. As a sizing engineer, I want to browse PV Transformer Stations and PV Inverters in separate
    catalogue sections, so that the station product and conversion product remain distinct.
32. As a sizing engineer, I want to open full specifications for both products, so that I can
    inspect either side of the pairing independently.
33. As a sizing engineer, I want separate station and inverter specification controls in the
    inspector, so that I can verify the exact products used by a placed station.
34. As a sizing engineer, I want every specification to lead with the parameters the engine
    consumes, so that simulated and typed parameters cannot be confused.
35. As a sizing engineer, I want typed fields grouped like the supplier datasheet, so that the
    product remains recognizable and reviewable.
36. As a sizing engineer, I want source URL, document version, date and market recorded, so that
    every transcribed value has visible provenance.
37. As a sizing engineer, I want unavailable typed fields shown as not published, so that absence
    is not mistaken for zero.
38. As a sizing engineer, I want a catalogue product with missing simulated data to be unavailable
    for selection, so that the engine never invents a required value.
39. As a sizing engineer, I want published 30 °C Sungrow transformer-station ratings populated,
    so that ambient sizing uses the supplier value already available.
40. As a sizing engineer, I want Huawei values used according to the project's declared
    engineering basis, so that 330 kW/kVA at 30 °C and 300 kW/kVA at 40 °C govern simulation.
41. As a sizing engineer, I want that Huawei engineering basis distinguished from the official
    datasheet fields, so that the interface does not misrepresent its provenance.
42. As a sizing engineer, I want obsolete TBEA catalogue entries removed, so that every selectable
    PV product follows the complete component format.
43. As a reviewer, I want the BESS catalogue and sizing behavior unchanged, so that the PV feature
    does not regress the other fleet kind.
44. As a reviewer, I want old projects removed rather than silently inferred or migrated, so that
    every surviving station satisfies the new required inverter contract.

## Implementation Decisions

### Keep the accepted topology and add composition, not a node

The station remains the only drawable MV/LV conversion point. An inverter is a catalogue
product selected within a PV station and never becomes a node kind, palette item or separately
connected diagram element. The accepted one-busbar-per-fleet topology and the shared POC/HV
equipment are unchanged.

The station's identity continues to be carried by its PV transformer-station product. Its new
inverter selection describes the conversion equipment behind that station. One station contains
one inverter product and a count; a fleet may mix station configurations.

### Keep catalogue data curated and on disk

PV inverters are loaded from a dedicated YAML catalogue alongside the existing catalogues. The
relational database remains project/design storage, not component storage. There is no catalogue
write endpoint or runtime product editor.

Catalogue-backed stations use catalogue-backed inverter pairings. Custom mode supplies a custom
transformer station and custom inverter values together; it does not create a reusable catalogue
entry.

### Use a small ambient-capability interface

The engine-facing inverter module exposes one concept: ambient-rated per-unit conversion power.
At a supported ambient, one scalar rating is both the active-power limit in kW and the
apparent-power limit in kVA because the accepted project rule interprets datasheet power at
power factor 1. Multiplying by the station's inverter count gives installed station capacity.

Every inverter has a required 40 °C value and an optional 30 °C value. Lookup never interpolates.
When 30 °C is requested but absent, the 40 °C value is used and a notice is returned. Unsupported
ambient values retain the existing conservative lookup principles rather than creating a curve.

This interface hides catalogue provenance, fallback selection and aggregate arithmetic from the
solver and result mappers. Callers consume resolved capacity and notices, not supplier-specific
fields.

### Treat supplier data and declared engineering data as separate provenance

Sungrow SG350HX-20 simulation ratings are 352 kW/kVA at 30 °C and 320 kW/kVA at 40 °C. Its
minimum power factor is 0.8. The typed specification preserves the official source's original
labels and units.

Huawei SUN2000-330KTL-H1 simulation ratings are 330 kW/kVA at 30 °C and 300 kW/kVA at 40 °C,
with minimum power factor 0.8. The ambient mapping is an owner-declared engineering basis and
must be labeled as such; it must not be presented as a temperature statement from Huawei. The
official nominal active, maximum active and maximum apparent fields remain typed supplier facts.

Project modelling guidance must record the general rule exposed by this decision: an explicit
owner-declared engineering value may supplement or override supplier literature only when the
simulation value and its non-supplier provenance remain visible. This is a surprising, durable
decision and should be recorded in the domain documentation or an accepted ADR rather than only
in code comments.

### Model pairings on PV transformer stations

A PV transformer station carries a pairing for each allowed inverter. A pairing provides the
maximum integer count, the default integer count and the provenance of those counts. The default
equals the maximum physical input count. A catalogue station with an unknown inverter, a count
below one or a count above the pairing maximum is invalid and does not solve.

Sungrow station pairings use SG350HX-20. Maximum/default counts are 10, 14, 20, 22 and 28 for
MVS3200-LV, MVS4480-LV, MVS6400-LV, MVS7040-LV and MVS8960-LV respectively. These counts come
from the published LV disconnector quantities and are explicitly an engineering interpretation
of physical inputs, not a supplier field named “maximum inverter count.”

Huawei station pairings use SUN2000-330KTL-H1. Maximum/default counts are 11, 22 and 30 for
JUPITER-3000K-H1, JUPITER-6000K-H1 and JUPITER-9000K-H1 respectively, from the published maximum
LV AC input counts.

Pairing is authoritative. Nominal AC voltage remains typed and visible but is not compared for
catalogue or custom stations.

### Preserve the POC requirement and move capacity authority to inverters

The POC target and requested power factor continue to define required delivered P and Q. The
existing backward loss/refinement solve remains responsible for finding inverter-side duty.
This feature does not make a plant export nameplate power merely because it is installed.

For the PV fleet, station shares are calculated from each station's aggregate ambient-rated
inverter capacity instead of its transformer-station rating. The refined inverter-side P and Q
are apportioned with the same share, so stations operate at a common per-unit conversion loading
even when their products or counts differ.

Each station is checked against both `P <= installed inverter power` and
`sqrt(P² + Q²) <= installed inverter power`. The two checks are deliberately retained even
though they share one power-at-ambient value: they describe different failure modes and keep the
interface ready for the operating point's active and reactive dimensions. The station's
inverter-side power factor is also checked against the catalogue minimum when present.

An inverter active-capacity, apparent-capacity or minimum-power-factor violation is a prominent
warning, not a solve error. Results remain available and state which station and limit failed.
Missing optional custom minimum power factor produces an unavailable-check notice rather than an
invented limit.

Transformer losses, MV output and current continue to be calculated from the P/Q allocated to
the station. Transformer loading is calculated against transformer-station AC power at ambient,
using the existing PV maximum-loading setting. Inverter limits always use 100% of their resolved
ambient rating and do not inherit the transformer loading percentage.

### Seed from the selected inverter arrangement

PV setup asks for transformer station, then one of its paired inverters, then inverter count per
station. The count defaults to the pairing maximum and is editable within the pairing range.

The setup flow derives station quantity from the number required to carry both the loss-adjusted
active and apparent conversion duty with that inverter arrangement. It may use the existing
bounded refinement strategy, but inverter capacity—not transformer-station rating—is the station-count
authority. The generated transformer's loading is checked separately and surfaced if the chosen
arrangement overloads it.

After generation, every station owns its configuration. Editing one station need not change its
peers, and recalculation uses the mixed fleet as drawn.

### Extend the diagram and catalogue contracts deliberately

The catalogue response gains PV inverter products and PV transformer-station pairing data. The
diagram station contract gains catalogue inverter selection plus integer count, or the custom
inverter fields required by custom mode. A PV station without a complete inverter configuration
is invalid.

Custom inverter input requires display name, 40 °C power, nominal AC voltage and count. The
30 °C power and minimum power factor are optional. Missing 30 °C power falls back to 40 °C with
a notice. Nominal voltage is stored and displayed but never validated.

The frontend and backend may introduce clearer types to distinguish PV transformer stations
from bare transformer electrical data, but the engine's transformer loss model remains shared
where behavior is genuinely common. Do not duplicate transformer equations to achieve naming
parity in the interface.

### Make the complete component format reusable

The specification view becomes product-generic rather than BESS-only. Every supported catalogue
product has stable brand/series/model identity, simulated parameters first, grouped typed
parameters, pairing information where applicable and source provenance.

PV transformer-station typed groups follow the source material: input/LV panel, output
transformer, ring main unit, auxiliary transformer, protection, optional features, general and
environmental, communications and standards. PV inverter typed groups cover efficiency, DC
input, AC output and grid support, protection, communications and connectors, general and
environmental, and standards.

The catalogue has distinct PV Transformer Stations and PV Inverters sections. Both are clickable.
A placed catalogue station exposes separate transformer-station and inverter specification
controls. Custom stations have no supplier specification view.

Missing simulated fields make a catalogue product unavailable for selection and generate a
catalogue-data failure visible to maintainers. Missing typed fields remain nullable and render as
“not published”; they are never coerced to zero or guessed.

### Upgrade the PV catalogue and remove TBEA

The supported transformer-station catalogue contains the five Sungrow MVS-LV products and three
Huawei JUPITER-H1 products. Sungrow's explicitly published 30 °C transformer-station ratings are
populated. Huawei continues to follow the accepted transformer-station fallback rule wherever
the supplier does not publish a separate 30 °C transformer-station rating.

All TBEA transformer-station entries are removed. SG350HX without the `-20` suffix,
SUN2000-330KTL-H2 and Huawei LUNA PCS products are not added.

### Reset rather than migrate

There is no backward-compatible inference for a station lacking an inverter. Existing projects
must not receive a synthetic “legacy inverter,” and old payloads stop solving until they satisfy
the new contract.

The user has explicitly authorized a permanent reset of the active default SQLite database with
no backup. At specification time it contains three projects and seven designs. The implementer
must resolve and display the exact selected SQLite target immediately before using the existing
reset mechanism; a different `DATABASE_URL` must not be assumed to be the authorized target.

### Update domain documentation

The glossary must be reconciled with the new model. In particular, **Station**, **Inverter**,
**Loading**, **Pairing**, **AC power at ambient** and **Simulated parameter / typed parameter**
must explain that a PV station has a selected inverter fleet, PV duty is allocated by installed
inverter capacity, transformer loading stays separate, and ambient inverter power uses explicit
lookup with declared provenance.

Accepted technology and topology decisions remain unchanged. The new owner-declared Huawei
ambient basis must be documented as an explicit decision rather than allowed to masquerade as
supplier data.

## Testing Decisions

A good test exercises behavior visible to an engineer or contract consumer: what the catalogue
returns, whether a complete diagram solves, which warnings it reports, how station duty is
allocated, what setup generates and what the interface renders. Tests should not pin YAML parser
helpers, private allocation steps or internal React state.

Use three existing seams, the fewest that cover the tiered application without inventing a
browser E2E framework:

1. **Diagram solve behavior is the primary seam.** Submit valid PV-only and hybrid diagrams
   through the existing diagram-to-engine interface and assert station allocation, inverter
   capacity, ambient lookup, transformer loading, warnings and returned station results. This
   seam exercises schema validation, diagram mapping, engine sizing and result mapping together.
   Prior art is the existing graph and calculation-correctness solve coverage.
2. **The catalogue and seed endpoints are the data-contract seam.** Assert that supported
   transformer stations expose their pairings, inverter products expose simulated/typed/provenance
   fields, removed products are absent, unavailable simulated data cannot be selected, and seeded
   station count is driven by the chosen inverter arrangement. Prior art is the existing
   catalogue, API and seed coverage.
3. **Rendered catalogue, setup and inspector behavior is the interface seam.** Render from a
   fixture catalogue and assert filtered selection order, count bounds/defaults, separate spec
   controls, complete grouped specifications, provenance labels, missing-data notices and absence
   of a standalone inverter palette item. Prior art is the existing specification-view,
   catalogue-page, palette and inspector component coverage.

Required behavioral cases include:

- Sungrow at 30 °C and 40 °C, proving both ambient capacity values and no interpolation.
- Huawei at 30 °C and 40 °C, proving the declared engineering values and their provenance.
- Missing 30 °C custom power, proving 40 °C fallback plus notice.
- Mixed station counts/models, proving allocation follows aggregate inverter capacity rather
  than transformer-station rating.
- Active-capacity overload, apparent-capacity overload and minimum-power-factor violation,
  proving each warns while results remain available.
- Transformer overload with adequate inverter capacity, proving the checks remain independent.
- Invalid inverter pairing and count outside the pairing range, proving the diagram does not
  solve.
- Catalogue and custom nominal-voltage mismatch, proving no voltage validation is performed.
- Seed generation where active capacity governs and another where apparent capacity governs.
- PV-only, active hybrid and BESS regression cases, proving topology and BESS behavior survive.
- Catalogue rendering for every supported PV product and explicit absence of TBEA, SG350HX,
  Huawei H2 and LUNA PCS entries.
- Specification rendering order, grouping, source link/version/date/market and distinction
  between supplier-published and owner-declared values.

Run focused engine/catalogue/API tests first, then the full Python suite. Run focused frontend
catalogue/specification/setup/inspector tests, then the full frontend test suite, production build
and lint using a disposable SQLite `DATABASE_URL`. Never use the authorized user database as test
setup.

## Out of Scope

- A standalone or draggable inverter canvas node.
- More than one inverter model within a single station.
- Runtime catalogue creation, editing or persistence in SQLite.
- Automated datasheet parsing or committed supplier PDFs.
- TBEA transformer stations or inverters.
- Sungrow SG350HX without `-20`, Huawei SUN2000-330KTL-H2 or Huawei LUNA PCS.
- Voltage compatibility validation for catalogue or custom equipment.
- Interpolated ambient derating curves or temperatures other than the supported explicit lookup.
- Detailed P-Q capability curves, asymmetric leading/lagging limits, MPPT modeling, DC strings,
  efficiency curves in the solver, clipping, harmonic behavior or time-series generation.
- Making inverter warnings block calculation.
- Changing the POC target, reactive split, shared export equipment or one-busbar-per-fleet
  topology.
- Changing BESS container, solution, PCS, pairing or auxiliary-load behavior.
- Migrating or backing up existing projects and designs.
- Editing products from the read-only specification view.

## Further Notes

The authorized database deletion is irreversible: three projects and seven designs will be
removed from the active default SQLite database without backup. The reset is an implementation
step, not test setup, and must occur only after the exact target is re-resolved.

Supplier provenance must preserve two deliberate distinctions. Sungrow's physical maximum count
is inferred from published disconnector quantities rather than a field named “maximum inverter
count.” Huawei's 30 °C/40 °C simulation values are an owner-declared engineering basis rather
than a temperature mapping stated in the official H1 datasheet. Both values are accepted for
simulation; neither may be relabeled as a direct supplier claim.

The design intentionally makes active and apparent nameplate capacity numerically equal at a
given ambient because inverter datasheet power is treated at power factor 1. Reactive duty still
matters: it increases apparent operating power and can fail the apparent-capacity check before
active power reaches its limit.

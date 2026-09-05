# Spec: Component datasheets in the catalogue — BESS first

Status: ready-for-agent

## Problem Statement

A sizing engineer cannot tell what any catalogue entry actually is.

Every BESS solution in the catalogue today is invented — the file that holds them says so, in
capitals, on every entry. None carries a brand, a series or a model number, so a solution is
identified in the interface by a bare key string that matches nothing on any supplier quote.
There is no record of which datasheet a number came from, and no way to read the rest of that
datasheet without leaving the tool.

The catalogue also has no home. A BESS solution appears in exactly one place — a dropdown in
the Inspector, reachable only after a station is already on the canvas. There is no way to
browse products, compare two of them, or look at one without opening a project first. Clicking
a BESS station in the palette shows "Loading…" indefinitely, because the preview looks the key
up in the PV catalogue only.

Underneath that is a modelling gap the first real datasheet exposes. The Sungrow PowerTitan 3.0
container is **transformerless**: it emits 690 V and reaches MV only through a station
transformer that its datasheet says nothing about. The tool already keeps BESS station
transformers in a separate catalogue, but nothing records which containers a given station
transformer is actually sold with, or how many of them it serves. An engineer can pair a
container with a station transformer that no supplier would quote together, and the tool will
size it happily.

## Solution

Catalogue entries become products: brand, series, model number, the full published
specification, and a link to the datasheet the numbers were transcribed from.

A **BESS solution** and a **BESS station transformer** are explicitly paired in the catalogue,
and the pairing carries the number of containers that station transformer serves. Choosing a
station transformer, then a discharge duration, narrows the solutions on offer to the ones that
are actually sold in that combination, and fills the container count in from the pairing.

Every component is browsable on a new catalogue page that does not require opening a project,
and any catalogue-backed component opens full-screen into a read-only specification view —
from the catalogue page, from the palette, or from a station already on the canvas. That view
leads with the handful of parameters the engine actually consumes, then shows the rest of the
published specification grouped the way the datasheet groups it.

The first real product in the catalogue is the Sungrow PowerTitan 3.0 ST6900UX-4H. The
placeholders are deleted.

## User Stories

1. As a sizing engineer, I want to browse every catalogue component on one page without opening
   a project, so that I can compare products before committing to a design.
2. As a sizing engineer, I want a BESS solution to carry a brand, a series and a model number,
   so that I can match a catalogue entry to a supplier quote.
3. As a sizing engineer, I want catalogue entries named by series first, so that I recognise a
   product the way the supplier markets it.
4. As a sizing engineer, I want to open a component's full specification full-screen, so that I
   can read it without squinting at a side panel.
5. As a sizing engineer, I want the parameters the engine consumes shown separately and first,
   so that I can see at a glance what the tool uses versus what the datasheet publishes.
6. As a sizing engineer, I want a link to the source datasheet, so that I can defend a number I
   put into a design review.
7. As a sizing engineer, I want to be told when a datasheet is marked preliminary, so that I
   treat its numbers with the right amount of caution.
8. As a sizing engineer, I want to choose a station transformer, then a discharge duration, and
   see only the BESS solutions sold in that combination, so that I cannot specify a pairing no
   supplier offers.
9. As a sizing engineer, I want the container count filled in from the pairing, so that I do not
   have to remember the ratio between a station transformer and its containers.
10. As a sizing engineer, I want to override that container count, so that I can model a
    partially populated station.
11. As a sizing engineer, I want a design that names an unpaired solution and station transformer
    to be rejected, so that a hand-edited payload cannot smuggle in an impossible station.
12. As a sizing engineer, I want to see which solutions a station transformer is sold with while
    looking at the station transformer, so that compatibility is discoverable from either side.
13. As a sizing engineer, I want to be told when a solution publishes no auxiliary consumption,
    so that I know the busbar auxiliary load is understated.
14. As a sizing engineer, I want that missing auxiliary figure treated as zero rather than
    blocking me, so that a gap in a datasheet does not stop me working.
15. As a sizing engineer, I want that notice repeated in design validation, so that it follows
    the number into the busbar total rather than only appearing where I first read it.
16. As a sizing engineer, I want to click a BESS station transformer in the palette and see its
    preview, so that the panel stops saying "Loading…" forever.
17. As a sizing engineer, I want BESS solutions in the palette alongside station transformers,
    so that products live in one place rather than half in a panel and half in a dropdown.
18. As a sizing engineer, I want the expand affordance hidden on custom stations, so that I am
    not shown a specification sheet with no specification in it.
19. As a sizing engineer, I want the specification view to be read-only, so that I can study a
    product without risking an accidental edit.
20. As a sizing engineer, I want to reach the specification view from a station already on the
    canvas, so that I can check what I placed without losing my diagram.
21. As a sizing engineer, I want cables and PV station transformers listed on the catalogue page
    too, so that the page is the one place I look for equipment.

## Implementation Decisions

### The catalogue stays on disk

Component data remains YAML files loaded once into the in-memory component database at
startup. No catalogue tables in the relational database, no write endpoints, no catalogue
editing at runtime. The pairing between a BESS solution and a BESS station transformer is a
YAML field.

Editing catalogue data from inside the application is a materially larger piece of work and is
not in this scope.

### A container keeps its share of conversion equipment

The glossary defines a **container** as one enclosure of battery cells *and its share of
conversion equipment*. That stands. A BESS solution remains a single record covering both
battery energy and PCS rating. A DC-only battery product — one with no PCS, which is a real and
common product shape — cannot be represented by this model, and that limitation is accepted
rather than designed around.

### Discharge duration selects a model; the duration table is deleted

`containers_by_duration` is removed from the BESS solution. Each solution declares a single
discharge duration.

The supplier's own model number already encodes it — `ST6900UX-**4H**` — and an engineer
procures against the model number, not against arithmetic. Sungrow's 6904 kWh across 4 × 450 kVA
computes to 3.84 h, and the nameplate still says 4H. **Discharge duration is declared, not
derived**, in the same sense and for the same reason that ADR-0002 makes technology declared
rather than derived.

The guarantee from the BESS module survives intact but changes its source: the durations offered
in the interface are the durations available among the solutions paired with the chosen station
transformer, so an unsupported duration remains unreachable by construction, and a payload naming
one is still rejected server-side.

### The pairing lives on the station transformer

A BESS station transformer carries a list of the solutions it is sold with, each with the number
of containers that station transformer serves. One station transformer pairs with few solutions;
one solution pairs with many station transformer ratings — so this is the shorter list to
maintain by hand. It is displayed from both sides.

Container count per station is read from this pairing. It is still never interpolated, derived
or rounded; it is now defaulted from the pairing and overridable by the engineer, because a
partially populated station is a real arrangement.

This supersedes the existing LV-voltage-match check as the primary compatibility rule. The
voltage check stays — a pairing whose voltages disagree is a data error worth catching — but it
is no longer the only thing standing between an engineer and an unbuildable station.

### Configuration order

Station transformer, then discharge duration, then BESS solution. The station is the thing
placed on the canvas, so the station transformer leads.

### Two tiers of parameter, and only two

Every catalogue field is either **simulated** — the engine reads it — or **typed**: structured,
stored, displayed, never computed with. There is no free-form tier. Prose rows such as a
fire-suppression component list or a compliance standard list are not stored at all.

BESS solution, simulated: nominal energy, PCS apparent power, PCS count, PCS LV voltage,
discharge duration, auxiliary active power, auxiliary reactive power.

BESS solution, typed: brand, series, model, cell chemistry, DC voltage window, AC voltage
window, AC current per PCS, power factor at nominal power, reactive power range, nominal
frequency, current distortion, isolation method, dimensions, weight, ingress protection,
corrosion class, operating temperature range, operating humidity range, maximum operating
altitude, cooling method, datasheet URL, datasheet version, preliminary flag.

BESS station transformer, simulated: the existing eight electrical parameters, unchanged.

BESS station transformer, typed: model, vector group, cooling, datasheet URL, paired solutions.

### PCS rating is stored as the datasheet states it

The current field is a single active-power figure in kW. Sungrow publishes apparent power in
kVA and a unit count: 450 kVA × 4. The field becomes apparent power per PCS plus a PCS count.

This carries no sizing risk today: PCS rating is passed through the catalogue endpoint but is
not consumed anywhere in the engine — only container energy is. The implementer must confirm
that remains true before renaming, and must not quietly introduce a consumer of it.

### A missing auxiliary figure is zero, plus a notice

Sungrow publishes no auxiliary consumption. A solution without one stores zero and raises an
**informational** notice — a new severity, distinct from the errors already raised for an
unknown solution or an LV mismatch. It appears in the specification view and again in design
validation, so it follows the understated figure into the busbar auxiliary load rather than
only appearing where the engineer first read it.

Nothing is blocked. A gap in a supplier's datasheet is not the engineer's error.

### Identity and naming

The catalogue key is a slug of brand and model. The display name leads with the series and
qualifies it with the model number — `PowerTitan 3.0 — ST6900UX-4H` — because the series is how
the product is recognised and the model number is what distinguishes two durations of it.

### Placeholders are deleted and the database is reset

Every existing BESS solution is placeholder data and is removed, replaced by the Sungrow entry.
Saved designs naming a deleted solution will fail validation with the existing unknown-solution
error. The database is reset as part of this work. **This destroys every existing project and
design and is not reversible.** At time of writing it holds one throwaway project of three
designs.

### The catalogue page

A new top-level route, independent of any project, listing all four catalogues: PV station
transformers, cables, BESS solutions, BESS station transformers. BESS entries carry the new
datasheet fields; PV station transformers and cables show what they already have. No technology
filter — the page belongs to no design, so there is no technology to filter by.

### The specification view

A full-screen overlay over the current view, dismissed with Escape, leaving the canvas mounted
beneath. Read-only; editing stays in the Inspector.

It leads with a compact block of the simulated parameters, then shows the typed specification
grouped as the datasheet groups it — DC side, AC side, physical, environmental — then the
pairings, then the datasheet link. Leading with the simulated subset is the point of the view:
the engineer must be able to see in one glance what the tool knows versus what the datasheet
says.

Three entry points: a row on the catalogue page, a selected palette item, and an expand control
in the Inspector for a catalogue-backed station. The expand control is **hidden** for custom
stations, whose parameters are typed by hand and have no datasheet behind them.

### Reused rather than rebuilt

The existing modal shell already provides a full-screen size and Escape handling; the
specification view uses it rather than introducing a second overlay mechanism. The existing
read-only detail-row and section-title idioms from the Inspector carry the specification rows.
The existing brand-grouping helper from the palette groups the catalogue listing. The existing
schema-check and database-reset script perform the reset — all of it is already built and
documented.

### Glossary and prior-decision conflicts

This spec **contradicts three glossary entries and one shipped ticket**, and they must be
updated as part of the work rather than left to drift:

- **BESS solution** and **Container** both define the container count as coming from "the
  solution's own table for the chosen discharge duration". That table is being deleted; the
  count now comes from the pairing on the station transformer.
- **Discharge duration** is defined as "restricted to whichever durations the chosen BESS
  solution actually offers". It is now restricted to the durations available among the solutions
  paired with the chosen station transformer.
- The BESS module's sizing ticket, already delivered, states container count is read from the
  duration table and is never overridable. Both halves change.

The datasheet-derived fields are a genuine addition to the domain and need glossary entries of
their own: the distinction between a simulated and a typed parameter, and the pairing itself.

## Testing Decisions

A good test here exercises behaviour the engineer can observe: what the catalogue endpoint
returns, what validation reports, and what renders. Not how YAML is parsed, and not the shape of
any intermediate structure.

Three seams, the fewest the change admits, each as high as it can go:

1. **The catalogue endpoint response.** One seam covering YAML loading, the reshaped component
   models and the serialised contract in a single assertion surface. Prior art: the existing
   catalogue tests, which already assert that every solution's parsed fields are present and
   positive.
2. **Design validation.** Pure functions in the graph layer, taking a design and returning
   issues. Prior art: the existing unknown-solution and LV-mismatch checks. This seam covers the
   new pairing rule, the reshaped duration rule, and the informational auxiliary notice —
   including that it is informational and does not fail a design.
3. **The catalogue page and specification view.** Component tests rendering from a fixture
   catalogue. Prior art: the existing frontend BESS tests, which already build a fixture
   catalogue of solutions by hand. Assertions: the simulated block renders before the
   specification, the grouping matches the datasheet's, the datasheet link is absent when the URL
   is empty, and the expand control is absent for a custom station.

The BESS module's golden snapshot pins numbers that the duration change moves. It must be
re-generated deliberately and the diff read, not regenerated blindly.

## Out of Scope

- Separating the battery container from its conversion equipment, and therefore any DC-only
  battery product.
- Datasheet fields for PV station transformers and cables. They appear on the catalogue page
  with the parameters they already have.
- Editing catalogue data in the application: no catalogue write API, no catalogue tables.
- Automated datasheet parsing. The Sungrow entry is transcribed by hand.
- Editing parameters from the specification view.
- Committing datasheet PDFs to the repository. Only a URL is stored, and it may be empty.
- Migrating existing designs. The database is reset instead.

## Further Notes

Two datasheets were read while writing this spec, and the second one is the reason the pairing
exists. Sungrow's PowerTitan 3.0 is a transformerless AC block at 690 V — it needs a station
transformer it does not describe. BYD's Haohan is DC only: no AC voltage, no power factor, no
isolation method, and its "nominal power" is a battery rating rather than a converter rating.
Modelling both would have required splitting the container from the PCS, which was considered
and rejected. Haohan is therefore unrepresentable, deliberately.

The three delivery slices are sequenced so that the only one able to break existing behaviour —
the data model — lands and is verified before any interface is built on top of it.

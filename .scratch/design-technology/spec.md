# Spec: Design technology, declared at creation

Status: ready-for-agent

## Problem Statement

Every design in the tool presents the same interface, regardless of what is being sized. A
PV-only design shows a "BESS target (MW)" field on its point of connection, a "Max loading —
BESS" override in its settings, and an "MV busbar — BESS" item in its palette. A BESS-only
design shows the PV equivalents. The engineer is asked, on every design, to ignore roughly
half of what is in front of them.

The tool does already know which fleet kinds a design contains — `takenBusbarSlots` reads it
off the drawn busbars, and the palette uses it to stop a second busbar of the same kind being
offered. But that knowledge arrives only *after* something has been drawn, so it cannot shape
the interface the engineer meets when a design is first opened, and it cannot be stated as an
intention: there is no way to say "this is a PV project" before drawing anything.

There is also no way to explore the same site under two arrangements. Turning a PV design
into a hybrid one, or reducing a hybrid design to its PV half, means redrawing by hand or
deleting work that may be wanted again.

## Solution

A design gains a **technology** — `pv`, `bess` or `hybrid` — chosen when the design is
created and stored on the design. The technology is a declaration, not a description: it
states what the design is for, and the interface is built to match it. Controls belonging to
a fleet kind the technology excludes are not shown, and palette items that would introduce
one are not offered.

Technology cannot be edited in place. It is changed by **cloning** the design into a new one
with a different technology, which converts the diagram to suit: a hybrid design cloned to PV
loses its BESS busbar and everything hanging off it, and a PV design cloned to hybrid gains
the ability to draw one. The original is never modified, so the destructive direction costs
nothing.

Alongside this, the user-controlled reactive split at the point of connection is removed. The
reactive duty of the shared HV transformer is divided between fleets pro-rata by active
power, always — which is what ADR-0001 already specified as the default. Each fleet carries
its own share and no more.

## Decisions

### Technology is declared and authoritative, not derived

The alternative was to compute technology from the drawn busbars and never store it, which
would have made disagreement between the stored value and the diagram impossible by
construction. Declaration was chosen because the interface has to be shaped before anything
is drawn, and because an engineer opening a design should be told what it is for rather than
having to infer it from what happens to be on the canvas.

The cost is accepted deliberately: there are now two places that know a design's fleet kinds,
and they can in principle disagree. See the enforcement decision below, and ADR-0002.

### Enforcement is at the palette only

A technology's exclusions are enforced by not offering the excluded items — not by rejecting
a save, and not by refusing to solve. A payload that contradicts its design's technology
(hand-edited, or imported) will be stored and solved without complaint.

This was chosen over save-time validation for interface reasons: the engineer never
encounters a rejection, because the action that would earn one is never available. The
residual risk is judged acceptable for a tool with one operator and no import path. ADR-0002
records the argument on both sides, because this is the decision a future reader is most
likely to question.

### Technology belongs to the design, not the project

A project can hold a PV design and a hybrid design of the same site, side by side, and they
can be compared. Every concept technology interacts with — the point of connection, fleets,
busbars — is already design-scoped in `CONTEXT.md`.

### Existing designs are deleted, not migrated

There is no migration mechanism (`Base.metadata.create_all`), and the designs currently in
`powertool.db` are test fixtures with no value. They are discarded rather than backfilled, so
`technology` can be a non-nullable column with no "unknown" state to thread through the code.

**This is irreversible and destroys every project and design in the database.** It is
authorised on the basis that the contents are disposable; confirm the file is disposable
before running it.

## Scope

### Data

- `Design` gains `technology`, a non-nullable string of `pv` | `bess` | `hybrid`.
- `DesignCreate` requires it. Design read schemas expose it.
- No diagram payload change. Technology sits beside the payload, not inside it.
- `powertool.db` is deleted and recreated empty.

### Creating a design

- The "New design" prompt becomes a two-field dialog: name, and a three-way technology
  picker. One step, built on the existing prompt dialog rather than a new wizard.
- Both fields are required; cancel behaves as it does today.

### Cloning a design

- A **Clone** action on each design row on the projects page, beside Delete.
- The dialog offers only legal target technologies:
  - `pv` → `hybrid`
  - `bess` → `hybrid`
  - `hybrid` → `pv` or `bess`
- `pv` ↔ `bess` is **not** offered in either direction. It would delete the entire diagram
  and produce a copy of nothing.
- The clone is a new design in the same project, named `<original> (PV)` / `(BESS)` /
  `(Hybrid)`.
- No confirmation dialog. The dialog states the consequence instead — "The BESS busbar, its
  stations and its circuits will not be copied" — because the original survives untouched.

**Conversion, narrowing (hybrid → pv, hybrid → bess):** the departing fleet's busbar, its
circuits, its stations, and any auxiliary load attached to that busbar are dropped from the
copied diagram. The departing fleet's point-of-connection target and its per-fleet maximum
loading override are cleared. For `hybrid → pv`, the discharge duration is cleared too.

**Conversion, widening (pv → hybrid, bess → hybrid):** nothing is added to the diagram. The
arriving fleet's point-of-connection target is set to zero and its busbar becomes available
in the palette. Automatically drawing a BESS fleet would require a solution and a duration to
be chosen first, which is a wizard, not a side effect of a button.

### Interface, per technology

Shown only when the technology permits the fleet kind:

| Element | Where | pv | bess | hybrid |
|---|---|---|---|---|
| "MV busbar — PV", PV station catalogue | Palette | yes | no | yes |
| "MV busbar — BESS", BESS station catalogue | Palette | no | yes | yes |
| "PV target (MW)" | Inspector, POC | yes | no | yes |
| "BESS target (MW)" | Inspector, POC | no | yes | yes |
| "Max loading — PV" override | Settings | yes | no | yes |
| "Max loading — BESS" override | Settings | no | yes | yes |
| Discharge duration section | Settings | no | yes | yes |

Everything else is technology-neutral and unchanged in all three: tier voltages, maximum
utilization, loss budgets, maximum circuit current, plant-wide maximum loading, auxiliary
loads, the HV transformer, and the whole results surface.

The discharge duration section already self-hides until a BESS station is drawn, so on a
`bess` design this changes nothing; the effect is on `pv`, where it can now never appear.

### Reactive split removal

- `q_share_pv` is removed from the point-of-connection node's properties, from the graph
  validator (including the `bad_q_share` issue), from the branch inputs, and from the
  reactive split function, which always divides pro-rata by active power.
- The control disappears from the inspector.
- ADR-0001 is amended to record the reversal.
- Any design payload still carrying `q_share_pv` is ignored rather than rejected — but note
  that no such design survives the database deletion above.

## Out of scope

- **Seeding a BESS or hybrid design.** The seed wizard builds a PV cascade from a
  point-of-connection target and stays that way. A BESS seed needs solution selection,
  discharge duration and container arithmetic before it can place a node — a separate
  feature, deliberately not folded in here. The consequence, stated plainly so it is not
  discovered half-built: a `bess` or `hybrid` design opens to a blank canvas and is drawn by
  hand, while a `pv` design can still be seeded.
- **Per-fleet power factor compliance.** Each fleet meeting the power factor target
  independently at its own branch is a different plant model that contradicts ADR-0001's
  single-interconnection-agreement argument, and it rewrites the multi-branch loss-refinement
  fixed point — the riskiest code in the tool, and the one part with no observable
  intermediate on the canvas. If it is wanted, it needs its own branch, its own golden test,
  and an ADR superseding 0001.
- Editing technology in place. Cloning is the only route.
- Any change to the solver beyond deleting the reactive-split override.

## Verification

- `pytest` — the full Python suite, including the graph validator's issue set with
  `bad_q_share` removed.
- `cd frontend && npm run build` — typecheck.
- `cd frontend && npm test` — vitest.
- `cd frontend && npm run lint` — oxlint.
- The pro-rata reactive split must reproduce, to within 1e-9, the results a hybrid design
  previously produced with `q_share_pv` unset. This is the one numerical claim the split
  removal makes, and it is the check that proves the removal changed no physics.

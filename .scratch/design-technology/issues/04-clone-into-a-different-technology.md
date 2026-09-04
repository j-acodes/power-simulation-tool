# 04: Clone a design into a different technology

**What to build:** A design's technology cannot be edited, but an engineer can copy a design
into a new one with a different technology. This is how a PV design becomes hybrid, and how a
hybrid design is reduced to either half — without losing the original, so the two arrangements
of the same site can be compared.

A Clone action sits on each design row on the projects page, beside Delete. Its dialog offers
only the legal targets for the design's current technology:

- `pv` → `hybrid`
- `bess` → `hybrid`
- `hybrid` → `pv` or `bess`

`pv` ↔ `bess` is offered in neither direction: it would delete the entire diagram and produce
a copy of nothing.

The clone is a new design in the same project, named after the original with its new
technology appended — `<original> (Hybrid)`. The technology is the reason the copy exists, so
it belongs in the name.

**Narrowing** (hybrid to a single technology) drops, from the copied diagram, the departing
fleet's busbar, its circuits, its stations, and any auxiliary load attached to that busbar. It
clears the departing fleet's point-of-connection target and its maximum loading override, and
for hybrid-to-PV it clears the discharge duration as well.

**Widening** (a single technology to hybrid) adds nothing to the diagram. The arriving fleet's
point-of-connection target is set to zero and its busbar becomes available in the palette;
the engineer draws the new fleet. Automatically drawing a battery fleet would require a
solution and a discharge duration to be chosen first, which is a wizard and is out of scope.

No confirmation dialog. The original survives untouched, so nothing is at risk — but the
clone dialog states the consequence of a narrowing conversion in words, naming the busbar,
stations and circuits that will not be copied.

The clone must be a valid design the moment it exists: it opens, solves, and its diagram
contains no node belonging to a fleet its technology excludes.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Each design row offers a Clone action whose dialog lists only the legal target
      technologies for that design
- [ ] Neither direction between PV and BESS is offered
- [ ] The clone is a new design in the same project, named after the original with its
      technology appended, and the original is unmodified
- [ ] Narrowing drops the departing fleet's busbar, circuits, stations and attached auxiliary
      load, and clears its point-of-connection target, its maximum loading override, and — for
      hybrid to PV — the discharge duration
- [ ] Widening changes no nodes and sets the arriving fleet's point-of-connection target to
      zero
- [ ] The narrowing dialog states in words what will not be copied
- [ ] A freshly cloned design opens and solves, and contains no node of an excluded fleet kind
- [ ] `pytest` passes
- [ ] Frontend typecheck, tests and lint pass

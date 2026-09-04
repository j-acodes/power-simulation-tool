# A design's technology is declared at creation and enforced only at the palette

A design now carries a **technology** — `pv`, `bess` or `hybrid` — chosen when the design is
created, stored on the design, and treated as authoritative over what the diagram may
contain. Controls and palette items belonging to an excluded fleet kind are not shown. The
technology cannot be edited; it is changed by cloning the design into a new one, which
converts the copied diagram to suit. Enforcement is by omission only: nothing rejects a saved
payload that contradicts its design's technology, and nothing refuses to solve one.

This is worth recording because it introduces a second source of truth for a fact the tool
could already compute, and then deliberately declines to defend it. Both halves of that will
look like oversights to a reader who does not have the argument in front of them.

## Considered Options

**Derive technology from the diagram and never store it.** The tool already computes this:
`takenBusbarSlots` reads which fleet kinds have a busbar, and the palette uses it to stop a
second busbar of the same kind being offered. Extending that into a named, computed
`technology` would have cost almost nothing and would have made disagreement between the
declared and drawn technology *impossible by construction* — there would have been only one
place that knew.

It was rejected because a derived technology can only describe a diagram that already exists.
The interface has to be shaped before anything is drawn, and a new design's canvas is empty:
a derived value would say "PV" about a blank design for no better reason than that PV is the
neutral default. Declaration also carries intent that derivation cannot — an engineer opening
a design is told what it is for, rather than inferring it from whatever happens to be on the
canvas. The judgement was that stating the intention up front is the actual feature, and a
derived value is not a cheaper version of it but a different, lesser one.

**Enforce the declaration at save time.** With technology authoritative, the natural
complement is a server-side check that refuses to store a diagram contradicting it, which
would restore the guarantee the derived option gave for free. This was recommended and
rejected: the engineer would meet a rejection for an action the palette never offered, which
is a worse experience than the drift it prevents. In a tool with a single operator and no
import path, the only route to a contradicting payload is hand-editing the database.

The cost is real and should be named. The stored technology and the drawn diagram *can*
disagree, and nothing will say so. A design hand-edited into that state will size whatever it
contains, using an interface built for something else. If an import path is ever added, or a
second operator, this decision should be revisited first — the check is small, and the reason
for omitting it is entirely about interface friction, not about difficulty.

**Editing technology in place.** Rejected in favour of cloning, because the narrowing
direction (hybrid to PV) deletes a whole fleet — its busbar, circuits, stations and auxiliary
load. As an in-place edit that is a destructive action needing a confirmation dialog and
still losing work. As a clone it is not destructive at all: the original survives, and the
two arrangements of the same site can be compared, which is a question a sizing engineer
actually asks. `pv` ↔ `bess` is not offered in either direction, because it would delete the
entire diagram and produce a copy of nothing.

## Consequences

The interface is built around exclusion rather than validation, so every place that shows a
fleet-kind-specific control now reads the design's technology. A control accidentally left
unguarded is invisible as a bug: it simply appears where it should not, and the engineer sees
a field for a fleet the design does not have — which is the state this decision exists to end.

Technology is non-nullable, which required discarding the designs already in the database
rather than backfilling them. They were test fixtures; this would not be available a second
time, and adding a genuine migration mechanism is the prerequisite for any future column.

Seeding remains PV-only. A `pv` design can still be seeded from a point-of-connection target;
a `bess` or `hybrid` design opens to a blank canvas and is drawn by hand. This is the sharpest
remaining interface difference between the technologies, and it is one this decision does not
address — deliberately, because a BESS seed needs solution selection, discharge duration and
container arithmetic before it can place a single node.

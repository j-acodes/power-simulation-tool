# Hybrid PV/BESS topology: one point of connection, a shared HV transformer, one busbar per fleet

A design can now carry two fleets — PV and BESS — behind a single point of connection, and
the topology that makes that possible is the subject of this record. The point of connection
carries a separate power figure per fleet rather than one undifferentiated figure. Below it,
a single shared HV transformer is sized once, on the two fleets' combined power and the power
factor target that already describes what the grid operator asks for at the point of
connection. Below the shared transformer, the two fleets no longer share a busbar: each fleet
gets its own MV busbar, its own circuits, and its own loading limit, sized as its own
independent cascade. The reactive duty the shared transformer must deliver is split between
the two fleets by an explicit, user-controlled share, defaulting to pro-rata by active power
but overridable when the project's reactive strategy calls for something else.

This is worth writing down because it is hard to reverse — the busbar-per-fleet kind rule and
the branch-shaped engine inputs it requires touch the diagram schema, the graph validator, and
the loss-refinement solver all at once — it is surprising without the reasoning in front of
you (a reader could easily expect either two fully separate connections or one shared
busbar), and it is the outcome of a genuine trade-off that was argued out and could have gone
either way.

## Considered Options

**Fully independent point-of-connection nodes, one per fleet.** This was the simplest model
to reason about: each fleet would size itself against its own POC power and its own power
factor target, with no interaction between them at all. It was rejected because it does not
match the physical plant. A hybrid project has one physical grid connection, not two — the
grid operator issues one interconnection agreement and states one power factor requirement
at one point, and a model with two independent POC nodes would have nowhere to put that
requirement without either duplicating it (and risking the two copies drifting apart) or
inventing a second, fictitious grid connection that does not exist on the ground. The shared
HV transformer is the direct consequence of taking the single physical connection seriously:
if there is one grid connection, there is one piece of export equipment sized against it.

**A single design that is either PV or BESS, with no hybrid case at all.** This was the
cheapest option on the table — roughly half the engineering effort of the hybrid model, and
by a wide margin the lowest-risk one, since it would have left the existing single-fleet
cascade and its loss-refinement fixed point completely untouched. It was rejected anyway,
despite that cost advantage, because hybrid PV/BESS behind one connection is an increasingly
common real project shape, and a tool that cannot represent it would fail the sizing engineer
on exactly the projects where getting the shared-connection interaction right matters most.
The team judged the extra cost worth taking on now rather than shipping a tool that solves an
easier problem than the one engineers actually have.

## Consequences

Taking on the hybrid case costs more than the two rejected options would have, in three
specific ways.

The uniform-per-unit-loading assumption — every station in a fleet running at the same
fraction of its rated power — used to be computed once, across every station on the canvas.
It now has to be computed once per fleet, because a PV station and a BESS station have no
business sharing a loading figure: they have different duty cycles, different maximum
loading limits, and mixing their power into one figure was exactly the modelling gap that
motivated giving stations a fleet kind in the first place.

The old validation rule — exactly one busbar, full stop — relaxes to exactly one busbar per
fleet kind. That is a real loosening of what the graph validator used to guarantee, replaced
by a narrower set of rules: no duplicate busbar of the same kind, and no station whose fleet
kind disagrees with the busbar it is drawn against. A single-fleet design is unaffected, but
the validator now has more to check, not less, and a design with a busbar-kind mismatch is a
new way for a drawing to be wrong.

The most expensive consequence is the loss-refinement fixed point. With one fleet, the
existing solver resolves a single circularity: a fleet's correction scalar changes the power
flowing through the shared cascade, which changes the losses, which changes the correction
scalar again, until it settles. With two fleets sharing one HV transformer, that circularity
becomes multi-branch: each branch's correction scalar now changes the combined flow through
the *shared* transformer, which changes the shared loss, which changes both branches'
requirements at once, not just its own. This is the riskiest part of the whole feature, and
it is also the one part with no observable intermediate on the canvas — there is no drawn
element a sizing engineer can point at mid-calculation to sanity-check that the split is
converging correctly. An error here would be invisible until the final delivered numbers came
out wrong. The outer fixed point is therefore bounded by an explicit iteration cap that
surfaces a non-convergence issue rather than ever returning a plausible-looking but incorrect
result, and the golden test for this feature is a hybrid design with zero BESS power, which
must reproduce the PV-only result to within 1e-9 — the one check available that exercises the new
multi-branch machinery while still having a known-correct answer to compare against.

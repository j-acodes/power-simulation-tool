# 06: Hybrid topology — canvas

**What to build:** An engineer can *draw* a hybrid plant as comfortably as a single-fleet
one, and cannot draw an invalid one.

The automatic layout currently finds the first busbar only, which would silently drop the
second fleet's stations into the unreached-node fallback columns — they would appear, but in
the wrong place, with no error. It must place every busbar, each with its own row and its own
horizontal band, and their stations beneath them.

Connection rules gain a check rejecting a station joined to the other fleet's busbar, and a
second busbar of a kind that already exists, so the invalid states ticket 05 rejects
server-side cannot be drawn in the first place.

The settings and point-of-connection inputs gain what the hybrid model needs: a power target
per fleet, the reactive share between branches, and a maximum loading per fleet kind.

**Blocked by:** 05 (Hybrid topology — engine and graph layer)

**Status:** done (d3c9eb5)

- [x] Automatic layout places both busbars and all their stations; no station falls into the
      unreached-node fallback in a valid hybrid design
- [x] The automatic-layout tests gain a two-busbar case
- [x] A station cannot be connected to a busbar of the other fleet kind
- [x] A second busbar of an existing kind cannot be added
- [x] The point of connection accepts a power target per fleet and a reactive share, with the
      share defaulting to pro-rata
- [x] Maximum loading can be set per fleet kind
- [x] A single-fleet design's layout is unchanged from before this ticket
- [x] Frontend typecheck, tests and lint pass; Python suite unaffected

## Review findings acted on (2026-09-04)

Two-axis review after implementation. Standards found one hard duplication
(`_max_loading` re-deriving the rules dict `_rule` exists to encapsulate, now split
into `_rule_opt`) and an overstated comment (`busbarFleetKind` claimed to *mirror*
the server; it deliberately diverges on the disputed-kind case, now stated and
pinned by a test).

Spec found three real defects, all fixed:

1. **The canvas duplicate check disagreed with the server.** Worse, the server
   disagreed with itself: `_busbars` read the *declared* kind while
   `_effective_busbar_kind` read the derived one, so a pre-hybrid BESS plant's
   undeclared busbar occupied the PV slot while being solved as a BESS branch —
   upgrading such a plant to a hybrid was rejected as a duplicate of a busbar that
   was not PV. `_busbars` now reads the effective kind; the canvas has `busbarSlot`
   (always answers, for the duplicate rule) alongside `busbarFleetKind` (may say
   "undecided", for what may connect).
2. **The Inspector's new fleet-kind select could create the duplicate** the palette
   and canvas both refuse. Taken kinds are now disabled, and say why.
3. **A busbar with no stations did not reserve its column**, so the next busbar laid
   out on the same spot — the normal mid-draw state.

One scope-creep finding kept deliberately: the aux column is now held clear of the
circuits. Positioned only relative to the spine centre it overlaps the last column
from six circuits up, which hybrids make markedly more likely. Both sides pinned.

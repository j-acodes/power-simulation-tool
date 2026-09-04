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

**Status:** ready-for-agent

- [ ] Automatic layout places both busbars and all their stations; no station falls into the
      unreached-node fallback in a valid hybrid design
- [ ] The automatic-layout tests gain a two-busbar case
- [ ] A station cannot be connected to a busbar of the other fleet kind
- [ ] A second busbar of an existing kind cannot be added
- [ ] The point of connection accepts a power target per fleet and a reactive share, with the
      share defaulting to pro-rata
- [ ] Maximum loading can be set per fleet kind
- [ ] A single-fleet design's layout is unchanged from before this ticket
- [ ] Frontend typecheck, tests and lint pass; Python suite unaffected

# 03: Domain vocabulary and the hybrid topology decision record

**What to build:** The project's shared vocabulary, written down for the first time, plus the
architecture decision record for the hybrid topology.

The project has no glossary today. This ticket creates one covering the terms this work
introduces or sharpens: **station**, **fleet kind**, **fleet**, **BESS solution**,
**container**, **PCS** (the battery-specific name for what the model calls the inverter
level), **discharge duration**, and **delivered energy**. The glossary is a glossary and
nothing else — no implementation detail, no decisions, no specifications.

Separately, record the hybrid topology decision: a single point of connection carrying a
power figure per fleet, a **shared HV transformer** sized on the combined requirement, **one
MV busbar per fleet** below it, and an **explicit reactive split** between the branches. This
qualifies for a decision record on all three counts — it is hard to reverse, it is surprising
without context, and it is the outcome of a genuine trade-off against fully independent
connections per asset class, which was considered and declined.

The record should also capture the two alternatives that were weighed and rejected: fully
independent point-of-connection nodes per fleet (rejected as not matching the single physical
grid connection), and one design being either PV or BESS with no hybrid at all (rejected
despite being roughly half the work).

This ticket gates nothing — documentation does not block code — but the vocabulary it fixes
should be used by every later ticket.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A project glossary exists at the repository root, defining every term listed above
- [ ] The glossary contains no implementation detail, file references or decisions
- [ ] An architecture decision record covers the hybrid topology, its consequences, and the
      two rejected alternatives with the reasons they were rejected
- [ ] Terms used in the decision record match the glossary exactly, with no synonyms

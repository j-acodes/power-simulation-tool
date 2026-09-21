# 06: Stage-1 planning opens busbars

**What to build:** when the tool plans the layout, it opens another busbar of the same fleet when
the next circuit would take the current busbar past 4000 A or past the feeders-per-busbar limit.
That limit is a new design setting, defaulting to 12, with a settings control and a PDF entry.
Drawn diagrams are unaffected.

**Blocked by:** 05.

**Status:** ready-for-agent

- [ ] A Stage-1 plan that fits one busbar is unchanged (golden baseline byte-identical for existing cases)
- [ ] A Stage-1 plan needing 13 circuits at the default setting produces two busbars
- [ ] A Stage-1 plan whose total would exceed 4000 A on one busbar opens a second one, whatever the feeder count
- [ ] The feeders-per-busbar setting is honoured when changed, shown in the settings panel (Vitest) and the PDF
- [ ] A drawn diagram with 13 circuits on one busbar is not rearranged
- [ ] Full README checks pass; report states that a DB reset is required (new settings key)

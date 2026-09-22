# 06: Stage-1 planning opens busbars

**What to build:** when the tool plans the layout, it opens another busbar of the same fleet when
the next circuit would take the current busbar past 4000 A or past the feeders-per-busbar limit.
That limit is a new design setting, defaulting to 12, with a settings control and a PDF entry.
Drawn diagrams are unaffected.

**Blocked by:** 05.

**Status:** done

- [x] A Stage-1 plan that fits one busbar is unchanged (golden baseline byte-identical for existing cases)
- [x] A Stage-1 plan needing 13 circuits at the default setting produces two busbars
- [x] A Stage-1 plan whose total would exceed 4000 A on one busbar opens a second one, whatever the feeder count
- [x] The feeders-per-busbar setting is honoured when changed, shown in the settings panel (Vitest) and the PDF
- [x] A drawn diagram with 13 circuits on one busbar is not rearranged
- [x] Full README checks pass; report states that a DB reset is required (new settings key)

## Comments

Shipped. Stage-1 fills busbars in the existing heaviest-first circuit order and opens the next
one past 4000 A or past `feeders_per_busbar` (rule, default 12, SeedRequest `ge=1`). The planning
estimate is the stations' MV output only: auxiliary load is not known at Stage-1 time. Golden
baseline byte-identical. DB reset required: new key `settings.rules.feeders_per_busbar`
(additive, code default 12). On a drawn diagram the setting shows in settings and the PDF but
changes nothing, since drawn diagrams are never rearranged. The seed wizard does not ask for it
yet; the API accepts it.

# 02: Cable entry bounds circuit cables

**What to build:** each transformer station declares its **cable entry** — cables accepted per
phase and maximum cable cross-section — as two simulated catalogue parameters. Unpublished
values fall back, in the engine and never in the YAML, to 2 cables of 630 mm² with a notice
naming the station. Every circuit cable must fit the stricter cable entry of its two ends: the
parallel-run limit is the lesser cables-per-phase, and cables above the lesser maximum
cross-section are excluded. The busbar end of a circuit's first cable counts as 2 × 630 mm².
Export cables keep today's `max_parallel` behaviour. The specification view shows cable entry
as a figure the engine reads. See CONTEXT.md "Cable entry" and ADR-0007.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] Catalogue load resolves an unpublished cable entry to 2 × 630 mm² and raises a notice (prior art: the 630 A switchgear fallback test)
- [ ] Cable selection for a circuit segment never uses more parallel runs, or a larger cross-section, than the stricter of its two ends allows
- [ ] A segment that no admissible cable can carry still solves and is flagged on that edge
- [ ] A station whose own current alone cannot be carried within its own cable entry raises a descriptive hard error
- [ ] Stage-1 grouping only forms circuits in which every segment has an admissible cable
- [ ] Export cable selection is unchanged (test pins that more than 2 parallel runs remain possible)
- [ ] Specification view marks cable entry as simulated (Vitest)
- [ ] Golden baseline regenerated only where numbers moved, with the reason in the commit message; full README checks pass

# 05: Scale to fit, then split onto continuation sheets

**What to build:** a busbar whose circuits and stations do not fit A3 at full size scales down
until they fit. If fitting would push text below 5 pt, the busbar's circuits split across
continuation sheets instead: each continuation repeats the busbar and is marked "continued from
sheet n" / "continued on sheet n"; circuits are never split across sheets. The grid-side chain
appears on the first sheet of the busbar.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] Layout-model tests: a small plant has scale 1 and one sheet; a medium plant scales below 1 with text at or above 5 pt and one sheet; a plant large enough to breach the floor splits, no circuit spans two sheets, continuation markers reference the right sheet numbers, and tags continue unchanged
- [ ] Browser check on a large design: downloaded SLD opened, continuation sheets screenshot and reported
- [ ] `tests/golden_baseline.json` byte-identical; full pytest, Vitest, build and lint pass

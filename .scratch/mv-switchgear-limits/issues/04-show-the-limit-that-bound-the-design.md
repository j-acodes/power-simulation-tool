# 04: Show the engineer which station bound their circuit

**What to build:** the engineer can see, without reading a stack trace or a PDF, what each
station is passing and what it is allowed to pass. Results show per-station through current
against switchgear rated current. A station running on the 630 A fallback rather than a
published figure is marked as such wherever the figure appears, so nobody mistakes a default for
a datasheet. The PDF report carries the same evidence, so the report supports its own verdict.

**Blocked by:** 03.

**Status:** ready-for-agent

- [ ] Results show each station's through current and the rating it was checked against.
- [ ] A fallback-sourced rating is visibly marked as defaulted in results, specification view
      and PDF.
- [ ] A non-compliant circuit visibly identifies the station that bound it.
- [ ] The PDF report shows through current against rating per station, and no longer mentions a
      current cap.
- [ ] Frontend tests cover the fallback marking and the bound-station display; vitest is run
      from `frontend/`, never the repo root.
- [ ] `npm --prefix frontend run build` and `run lint` pass with no new warnings.

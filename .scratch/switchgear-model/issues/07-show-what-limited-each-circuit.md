# 07: Show what limited each circuit

**What to build:** for every circuit, results and the PDF report name the limit that decided its
size — one of station switchgear, feeder, cable entry, or feeders per busbar — and show each
station's through current beside its switchgear rated current. Every fallback used (switchgear
rated current, cable entry) is visible as a notice. Absorbs the superseded ticket 04 of
`mv-switchgear-limits`.

**Blocked by:** 02, 04, 06.

**Status:** ready-for-agent

- [ ] Each Stage-1 circuit reports exactly one binding limit; a test covers each of the four
- [ ] A drawn circuit reports the limit it is closest to, not a planning decision it did not take
- [ ] Results table shows through current vs switchgear rated current per station (Vitest)
- [ ] PDF carries the binding limit per circuit and the per-station figures
- [ ] Full README checks pass, plus a browser check of the results view against a disposable DB

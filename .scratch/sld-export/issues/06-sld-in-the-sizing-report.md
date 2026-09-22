# 06: SLD sheets in the sizing report

**What to build:** the PDF sizing report shows each SLD sheet after the summary (and after the
notices, if present), scaled to the A4 text width as vector graphics, each with a caption that
names the sheet and says the legible version is the standalone Download SLD file. The report and
the standalone SLD are built from the same sheets, so they cannot differ.

**Blocked by:** 01 (for mechanism); schedule after 05 so the embedded sheets are complete.

**Status:** ready-for-agent

- [ ] Report-story test: one drawing flowable plus caption per SLD sheet, placed after the summary/notices and before the methodology; a hybrid design gives two
- [ ] Browser check: downloaded report opened and the embedded sheet page screenshot reported
- [ ] `tests/golden_baseline.json` byte-identical; full pytest, Vitest, build and lint pass

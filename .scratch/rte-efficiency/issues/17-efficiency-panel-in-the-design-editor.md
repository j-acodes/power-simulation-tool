# 17: Efficiency panel in the design editor

**What to build:** From the design editor, the engineer opens an **Efficiency** panel, uploads
a CSV of `timestamp, ambient °C`, sets cycles per day (and optionally overrides the cell
round-trip efficiency), and runs the efficiency run against the design currently on the
canvas. The panel shows:

- a time chart of operating RTE %, idle loss % per hour and PCS power % of rated;
- a summary: minimum, average and maximum operating RTE, average idle loss, and the number of
  timestamps where PCS derating applied;
- the run's warnings (clamped ambients, nearest cycles-per-day table, missing curves), and a
  clear error message when the run refuses (no BESS fleet, solution without rated active
  power, invalid design);
- a **Download CSV** button giving the four-column output exactly as the CLI writes it.

This exposes the existing engine function (tickets 12–16) through the API; it adds no new
physics. Owner decisions, 2026-10-23: inside a design only (no standalone typed-in page);
chart, summary and CSV download.

Scope:

- A new API endpoint that takes the diagram JSON, the ambient rows, cycles per day and an
  optional cell RTE, and returns the rows and warnings. Its request and response schemas are a
  new API contract; existing endpoints are unchanged. A run error is a 400 with the message.
- The frontend panel, opened from the editor header like Settings. The CSV is parsed in the
  browser; a header row is expected; bad rows are reported, not silently skipped.
- The chart is drawn without adding a chart dependency, readable in light and dark themes, and
  at a year of hourly data (8,760 points) stays responsive.
- Vocabulary from `CONTEXT.md` in UI copy: efficiency run, operating round-trip efficiency at
  the point of connection, idle standby loss, PCS derating, cycles per day.

**Blocked by:** 16

**Status:** ready-for-agent

- [ ] Running the panel on a seeded 100 MW / 4 h BESS design with a 25 °C row gives the same
      operating RTE as the CLI's `--diagram` run of that design.
- [ ] A 48 °C row shows PCS power 76 % and is counted as derated in the summary.
- [ ] The downloaded CSV is byte-for-byte the CLI's output format (header and rounding).
- [ ] A design with no BESS fleet shows the run's error message; warnings are listed.
- [ ] Backend tests for the endpoint (isolated database) and Vitest tests for CSV parsing,
      summary and the panel; the README checks pass apart from the known pre-existing
      failures.

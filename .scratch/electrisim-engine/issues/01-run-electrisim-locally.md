# Run Electrisim end-to-end locally

**Type:** task (AFK)
**Status:** open
**Blocked by:** None

## Question

Get the Electrisim fork running locally (backend on its existing `.venv`, frontend served
as static files) and run each in-scope study on a small PV/BESS plant so later decisions
can judge real behaviour: load flow, IEC 60909 short-circuit, POI fault study, grid-code
P-Q, grid-code U-Q, BESS preliminary design.

Known blocker to clear: study dialogs may still call the absent subscription API
(`stripe-subscription.js` → `localhost:5502/api/stripe/check-subscription`) and refuse to
run; the maintenance banner pings `localhost:5502/api/health`. CDN libraries (leaflet,
ag-grid, xlsx-style) need internet.

Work happens on a `chore/` branch in `rea-power-system-sim`. The answer records: start
commands, what was changed to make studies run, which studies worked or failed, the
sample plant used (saved under `projects/`), and inputs each study demanded that this
tool's catalogue does not have.

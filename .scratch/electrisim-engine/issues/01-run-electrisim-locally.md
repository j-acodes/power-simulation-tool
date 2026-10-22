# Run Electrisim end-to-end locally

**Type:** task (AFK)
**Status:** resolved
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

## Answer

All six in-scope studies run locally and return results on a small PV/BESS plant. Nothing
in Electrisim had to change: the earlier local-mode commit (`dc0d5dc`, login/Stripe
removed) already makes every study dialog's subscription check pass.

**Assets** (branch `chore/run-electrisim-locally` in `rea-power-system-sim`, commit
`c1b567c`): `projects/pv-bess-sample/` holds the start commands (`README.md`), a driver that
posts frontend-shaped payloads to the backend (`run_studies.py`), and every payload and
response. These responses are the Electrisim side of any later cross-check.

**Start:** backend `backend/.venv/Scripts/python.exe app.py` (port 5000); frontend
`python -m http.server 5500` in `frontend/src/main/webapp` (any loopback port passes CORS).

**Sample plant:** POC 132 kV (Sk" 2000 MVA) → 132/30 kV 15 MVA → 30 kV collector → PV
station (6 MW / 6.6 MVA, 30/0.8 kV) and BESS station (5 MW / 20 MWh / 5.5 MVA, 30/0.69 kV),
31.5 kA CB at the POC. Each study was also re-run with PV only and BESS only.

**What each study does** (detail and numbers in the asset README):

- **Load flow** works (9 s cold start). Storage uses pandapower's load sign, so +P means
  charging. That answers part of the "BESS import direction" question.
- **IEC 60909** works. The PV adds k·In; **storage adds no fault current**. The dialog's
  LV voltage tolerance (6 %) is never applied, and pandapower's 10 % is always used
  (confirms the known defect).
- **POI fault study** runs, but breaker duty uses **ANSI/IEEE C37.010** even at 50 Hz, PV
  and BESS contributions both come out as 0, and every IEC 60909 coordination case fails
  with a pandapower 3.3.2 error (`'_is_elements_final'`). It is not usable for IEC as it
  stands.
- **Grid-code P-Q** works for PV. **Storage can't be selected from the UI**: the backend
  needs a `storage_names` field that no dialog sends. In the hybrid run it pushed the 6.6
  MVA PV to the plant's 11 MW and left the BESS at its diagram set point. With no Q curve
  it falls back to a circular √(Sn²−P²) limit. It reports "compliant" while POC-side
  voltages reach 0.78–1.17 pu and the HV transformer 128 % loaded, unless the protection
  and overload limits are switched on.
- **Grid-code U-Q** behaves like P-Q, with no storage path at all. The hybrid run
  collapses to one point. Single-technology runs give sensible curves.
- **BESS preliminary** works for a **standalone** BESS only. With the PV in service, every
  import case fails. BESS-only: the export cases fail because a 5 MW PCS delivers 4.93 MW
  at the POC after losses, which is a genuine engineering result. The OLTC tap is solved
  per case.

**No study handles PV and BESS together.** Hybrid P-Q capability is not something
Electrisim can show us. It has to be designed here.

**Inputs the studies used that this tool's catalogue lacks:** grid Sk" max/min, R/X and
zero-sequence ratios at the POC; inverter/PCS `k` factor and current-source flag;
transformer vector group, zero-sequence impedance and tap range/step; numeric breaker
rating (`in_ka`); the BESS PCS Sn and Q limits; the grid-code envelope itself.

**Not covered:** the studies were not clicked through in a browser (the Chrome extension
was not connected). The payloads match `prepareNetworkData()` field for field, and all
pages and scripts serve with HTTP 200. Offline behaviour of the CDN libraries was not
checked.

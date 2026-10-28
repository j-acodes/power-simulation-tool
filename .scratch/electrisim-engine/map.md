# Map: Network solve from the Electrisim engine

**Label:** wayfinder:map

## Destination

Three artefacts under `.scratch/electrisim-engine/`, ready to hand to implementation: a
ranked **roadmap** of the Electrisim capabilities this tool adopts, a locked decision on
**how the engine comes in** (recorded as an ADR), and a hand-off-ready **spec** for the
first capability on the roadmap.

## Notes

- Domain: `CONTEXT.md` (new term **Network check**) and `docs/adr/`. Use **POC**, never
  Electrisim's "PCC". The sizing ADRs (0001–0009) stand: nothing in this effort changes how
  a design is sized.
- Every session consults the `grilling` and `domain-modeling` skills.
- Source under study: the Electrisim fork at
  `C:\Users\JavierAguilar\my-projects\power-sim-upgrade\rea-power-system-sim` (Flask +
  pandapower 3.3.2 backend, mxGraph frontend). Its engine is a reference, not a requirement.
- Settled framing (charting session, 2026-10-22):
  - **Network check, not network sizing.** The loss cascade stays the sizing method. A
    load-flow and short-circuit solve runs on the sized design and reports what it finds;
    it never changes a selection.
  - **Capabilities in scope:** load flow (voltages, currents, reactive power, losses at the
    POC); IEC 60909 short-circuit including inverter/PCS contribution and the POI fault
    study (source contributions, breaker duty against switchgear ratings); grid-code P-Q
    and U-Q capability at the POC; the BESS operating-case checks (export/import ×
    capacitive/inductive at Umin/Unom/Umax).
  - **IEC only, 50 Hz.**
  - **Electrisim is a reference only** (user decision, 2026-10-22, after the licence answer):
    no Electrisim code is copied, vendored or run as a service by this tool. Sessions read
    it for method and behaviour, then write this tool's own code against pandapower.
  - **Grid-code markets:** Spain, Portugal, Poland, France, Croatia, Italy, Germany.
  - **Calculation and logic only.** The React Flow canvas stays; no Electrisim UI is ported.
  - **On demand** (user decision, 2026-10-22): the network check runs only when the user
    asks for it, never on the automatic re-solve after an edit.
- Scouting facts (2026-10-22) any ticket may lean on:
  - This tool's engine is stdlib + YAML; there is no nodal solve, voltage, short-circuit or
    Q-capability calculation anywhere in `powertool/`.
  - Catalogues already carry load-flow inputs (cable R/X/B per km; transformer uk, Pk, P0,
    i0). They lack short-circuit inputs: inverter/PCS fault contribution, transformer
    vector group and zero-sequence, numeric switchgear short-time withstand, and grid
    short-circuit power at the POC.
  - Electrisim's grid-code P-Q/U-Q, BESS-preliminary and short-circuit modules run on a
    plain pandapower net (its `samples/test_*.py` do so) but import the 15k-line,
    frontend-coupled `pandapower_electrisim.py`. `storage_q_capability.py`,
    `converter_sc_electrisim.py` and `sc_fault_location.py` are standalone.
  - Defects seen in Electrisim, so nothing is copied unverified: `lv_tol_percent` computed
    but not passed to `calc_sc`; BESS-preliminary passes Q mode `'from_curve'`, which the
    P-Q engine does not recognise (falls to Sn/2); the ANSI 1-ph zero-sequence network omits
    transformers; storage gives no IEC 60909 contribution; the POI study's IEC cases all
    error and its breaker duty is ANSI; P-Q/U-Q dialogs cannot select storage (see
    "Run Electrisim end-to-end locally").
  - Electrisim's grid-code envelopes live in its frontend (`dialogs/RPCDialog.js`); the
    backend P-Q sweep only takes an envelope as input.

## Decisions so far

<!-- one line per resolved ticket: [title](issues/NN-slug.md): gist -->

- [Run Electrisim end-to-end locally](issues/01-run-electrisim-locally.md): all six studies run on a PV/BESS sample plant (payloads and responses saved for cross-checks); no study handles PV and BESS together, storage adds no fault current, the POI study's IEC part fails.
- [What reactive-power envelopes do the target markets require at the POC?](issues/03-grid-code-reactive-requirements.md): primary sources found for all seven markets (Germany only via summaries); Electrisim's templates are mostly wrong or missing, so envelopes become this tool's own data; Spain and Italy have storage charging-mode rules.
- [Under what licence is Electrisim's backend published?](issues/02-electrisim-backend-licence.md): no licence file upstream, only a README claim of Apache-2.0; reading is free, copying needs the claim confirmed by the owner; depending on pandapower/lightsim2grid is fine; ANDES is GPL.
- [How does the network solve come into the engine?](issues/04-how-the-engine-comes-in.md): own `powertool/network/` package taking the sized design plus a POC grid equivalent, returning its own pass/warn/fail results; pandapower pinned 3.3.2, no numba/lightsim2grid; separate network baseline plus Electrisim and hand-calc cross-checks (ADR-0011).
- [Where do short-circuit inputs come from?](issues/05-short-circuit-input-data.md): grid Sk" max/min and X/R are a required per-design input (no placeholder; check skipped with a warning); converter k, transformer zero-sequence and numeric switchgear withstand are datasheet catalogue fields with declared defaults; first check is three-phase only; PV station "withstand" strings are really IAC ratings.

## Not yet specified

- **Hybrid capability**: how PV and BESS Q capability combine at one POC. No Electrisim
  study models both together, so there is no reference behaviour to copy.
- **Transformer taps**: the catalogue has no tap data; P-Q/U-Q sweeps depend on tap
  position.
- **Where results surface**: issue vs warning vs a compliance verdict, and how a check reaches
  the API, results tables and PDF report.
- **Grid-code envelope data**: where envelopes live (a `data/` catalogue like the others?),
  how a P-Q, a U-Q and a charging-mode envelope are represented, how a design selects its
  market, type (B/C/D) and voltage variant, and how each envelope carries its source.
- **Spec assembly** for the first roadmap capability, with acceptance criteria and a
  worked example checked against Electrisim's result on the same plant.

## Out of scope

- Harmonics, arc flash, motor starting, ANDES dynamics, OpenDER/IEEE 1547 behaviour,
  data-centre site screening: they do not move PV/BESS sizing decisions.
- ANSI/IEEE C37 short-circuit and 60 Hz studies.
- Electrisim's BESS "sizing" (a power-target solve); this tool's energy sizing is ahead.
- Electrisim's mxGraph UI, auth, payments and cloud-storage integrations.
- Using load flow to size equipment (replacing the loss cascade).

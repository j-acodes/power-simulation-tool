# What reactive-power envelopes do the target markets require at the POC?

**Type:** research
**Status:** resolved
**Blocked by:** None

## Question

For Spain, Portugal, Poland, France, Croatia, Italy and Germany: which document sets the
reactive-power requirement at the connection point for PV and BESS power park modules
(by NC RfG type B/C/D and connection voltage), and what are the P-Q envelope and U-Q
envelope values (Q/Pmax limits against P and against voltage, voltage bands, any
storage-specific or import-mode rule)? Name document, version and clause for each.

Then compare against Electrisim's templates in
`rea-power-system-sim/frontend/src/main/webapp/js/electrisim/dialogs/RPCDialog.js`
(P-Q ~lines 9–170, U-Q ~177–220): which markets are present, which match the sources, and
which are missing (Portugal, France and Croatia were not seen when charting).

## Answer

Q/Pmax below: + injecting, − absorbing.

| Market | Source | Envelope | Confidence |
|---|---|---|---|
| Spain | Orden TED/749/2020 Anexo I §2.3.2; TED/82/2026 makes storage meet it when charging | ±0.30 for P ≥ 0.2; U-Q a slanted 0.30-wide band over 0.95–1.05 pu | High |
| Portugal | Portaria 73/2020, points 14, 18, 19 | −0.33/+0.41 (< 110 kV, type B); −0.40/+0.30 (type D ≥ 110 kV) | High / Medium |
| Poland | PSE Wymogi 2025 (in force 2025-12-01, replaces 2019 for new projects) | −0.35/+0.40 at 0.1–0.9 P; U-Q per 400, 220/110 and < 110 kV | High |
| France | Arrêté 9 juin 2020 Art. 41 + RTE DTR 5.1.1 v1.2 (transmission); Art. 43 (distribution) | −0.35/+0.32, shift up to +0.13; distribution +0.40/−0.35 within ±5 % Uc | High / Medium |
| Croatia | HOPS mrežna pravila, NN 10/2024, čl. 145, 153 | ±0.33; U-Q a rectangle 0.875–1.10 pu | High |
| Italy | Terna A.68 Rev.04 (PV); A.79 Rev.00 (BESS) | PV ≥ 110 kV −0.35/+0.30; BESS −0.48/+0.30 at rated P in both directions, −0.90/+0.72 at P = 0 | High (newer revisions possible) |
| Germany | VDE-AR-N 4120 variants 1–3 (+0.48/−0.23, +0.41/−0.33, +0.33/−0.41); 4110 ±0.33 | from summaries; texts paywalled; 4130 not obtained | Medium / Low |

Electrisim's templates (frontend `RPCDialog.js`; the backend sweep only takes an envelope as
input) do not hold up as a source: of its 13 templates for these markets, 3 match a current
primary source (Polish 400 kV U-Q, Polish 2019 Fig. 2 P-Q) and 2 roughly match (VDE 4120
Var. 2 and 4110, at full P only). The Italian A.68 and both ENTSO-E templates have wrong
values, and the Polish "110 kV" U-Q is actually Croatia's rectangle. The Polish cos φ
templates are untraceable, and the Spanish one is mislabelled P.O. 12.2 (wind; ±0.3287
instead of ±0.30). Portugal, France and Croatia are missing, as are U-Q envelopes for Spain,
Italy and Germany and any charging-mode envelope.

Consequence: grid-code envelopes are this tool's own data, built from the sources above,
not imported from Electrisim. Storage import-mode rules exist (Spain, Italy) and must be
expressible.

Still unverified: German standard texts, Enedis U-Q diagram, CEI 0-16, type thresholds, and
storage rules for Portugal, France and Croatia. Detail and sources: branch
`research/grid-code-reactive-requirements`,
`.scratch/electrisim-engine/research/grid-code-reactive-requirements.md` (§9 lists the gaps).

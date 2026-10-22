# Grid-code reactive-power envelopes at the POC: seven target markets

Research for ticket `issues/03-grid-code-reactive-requirements.md`. Researched 2026-10-22.

Conventions used in every table below:

- Q is expressed as Q/Pmax. **Positive Q = production / over-excited / capacitive (injecting vars)**,
  negative Q = consumption / under-excited / inductive. Where a source uses another sign
  convention it has been converted, and this is noted.
- "P-Q" = reactive capability below maximum capacity (Q vs P at nominal voltage).
  "U-Q" = reactive capability at P = Pmax vs POC voltage (pu).
- All requirements are at the **POC** (point of connection) unless stated otherwise.
- Confidence: **High** = values read directly from the primary text or its figures.
  **Medium** = read from a figure without printed coordinates, or from the standard owner's own
  summary rather than the standard itself. **Unverified** = not confirmed from a primary source in
  this pass. Nothing marked Unverified should be put into a template without a further check.

---

## 0. EU baseline: Regulation (EU) 2016/631 (NC RfG)

Source text read: the original adopted text of Articles 20 and 21 (EUR-Lex blocks automated
fetches, so the adopted version mirrored on legislation.gov.uk was used:
<https://www.legislation.gov.uk/eur/2016/631/article/21/adopted>, `/article/20/adopted`).

| Clause | Scope | What it sets |
|---|---|---|
| Art. 20(2)(a) | Type B PPM | "the relevant system operator shall have the right to specify" the reactive capability. **No numeric envelope in the RfG.** |
| Art. 21(3)(b) | Type C PPM (and D through Art. 25 for offshore, and through Art. 21 applying to D) | System operator, with the TSO, sets a U-Q/Pmax profile at Pmax. It must sit inside the fixed outer envelope (Fig. 8) and not exceed the inner-envelope dimensions in Table 9. |
| Art. 21(3)(c) | Type C/D PPM | System operator sets a P-Q/Pmax profile. Its Q range is bounded by Table 9. It must include a rule for Q at P = 0. |
| Art. 21(3)(d)(ii) | Type C/D PPM | Voltage-control setpoint range 0.95–1.05 pu, slope 2–7 %. |

**Table 9 (Continental Europe).** These are the *maximum* range a system operator may require,
not a minimum:

| Synchronous area | Max range of Q/Pmax (total width) | Max steady-state voltage range (pu) |
|---|---|---|
| Continental Europe | **0.75** | **0.225** |
| (Nordic / GB / IE-NI / Baltic for reference) | 0.95 / 0.66 / 0.66 / 0.80 | 0.150 / 0.225 / 0.218 / 0.220 |

The fixed outer envelope of Fig. 8 runs from Q/Pmax −0.50 to +0.65 and from U = 0.875 to 1.10 pu.
This shows as the black box in PSE's 2019 figure (Poland section). Confidence: High for Table 9,
Medium for the outer-box coordinates (read from the PSE reproduction).

**The RfG sets no storage rule.** Storage is outside RfG 2016/631, so each member state decides
whether storage follows generator rules, and in which modes.

---

## 1. Spain

**Documents**

- **Orden TED/749/2020, de 16 de julio**, Anexo I §2.3.2 "Capacidad de potencia reactiva" (PPM).
  BOE-A-2020-8965, BOE nº 208 of 1 Aug 2020, pp. 62426–62428, Figures 10, 11 and 12.
  <https://boe.es/boe/dias/2020/08/01/pdfs/BOE-A-2020-8965.pdf>
- **Orden TED/82/2026, de 9 de febrero**, which amends TED/749/2020 and adds a new *Disposición
  adicional primera* on storage. BOE-A-2026-3213, BOE nº 38 of 12 Feb 2026.
  <https://boe.es/boe/dias/2026/02/12/pdfs/BOE-A-2026-3213.pdf>
- P.O. 12.2 (Resolución 1 Feb 2018) is the pre-RfG procedure. TED/82/2026 now cites it only for
  small non-peninsular PPMs (FRT). It is **not** the reactive-capability source for new RfG PPMs.

**Scope by type.** Types D, C and B ≥ 15 MW get the full requirement (§2.3.2.1, with B/C pointed
to it by §2.3.2.2). Types B and C with Pmax < 15 MW need only the solid-line U-Q profile of Fig. 12,
without the dashed extensions. The reactive requirement is at the POC, and the PPM must compensate
everything between the plant and the POC.

**P-Q (Fig. 11, all PPM types B/C/D)**

| P/Pmax | Q_min | Q_max |
|---|---|---|
| 0 – 0.1 | −0.05 | +0.05 |
| 0.1 | −0.15 | +0.15 |
| 0.1 → 0.2 | linear −0.15 → −0.30 | linear +0.15 → +0.30 |
| 0.2 – 1.0 | **−0.30** | **+0.30** |

Operating points with |Q| between 0.2 and 0.3 Pmax may take up to 1 min (no fast-response
requirement there).

**U-Q at Pmax (Fig. 10 type D; Fig. 12 B/C < 15 MW = solid part only).** This is a parallelogram,
not a rectangle. The total width is always 0.30.

| U (pu) | Q_min | Q_max |
|---|---|---|
| 0.90 (dashed, D and B/C ≥ 15 MW only) | 0 | +0.30 |
| 0.95 | 0 | +0.30 |
| 1.00 | −0.15 | +0.15 |
| 1.05 | −0.30 | 0 |
| 1.10 (dashed; 110–300 kV) or 1.0875 (dashed; > 300–400 kV) | −0.30 | 0 |

Outside 0.95–1.05 pu, active power has priority over reactive. The dashed-extension capability may
take up to 1 min and may rely on the OLTC.

**Storage (TED/82/2026, DA 1ª).** Until a specific storage code is approved, storage must meet the
PGM requirements **in both injection and absorption modes**. In absorption mode, Pmax = the maximum
power the storage can absorb from the grid continuously. Type thresholds use Pmax in injection mode.
This means the P-Q envelope above has to be mirrored into the charging (P < 0) half-plane, with
the absorption Pmax as the base.

**Type thresholds** (RD 647/2020; B ≥ 100 kW, C ≥ 5 MW, D ≥ 50 MW or ≥ 110 kV): **Unverified**
in this pass.

**Confidence: High** for envelopes and the storage rule. They were read from the BOE figures,
which print axis values.

---

## 2. Portugal

**Document.** **Portaria n.º 73/2020, de 16 de março**, Anexo "Requisitos não exaustivos do RFG",
DR 1.ª série n.º 53, pp. 41–56. It revokes Despacho 3306/2018.
<https://files.dre.pt/gratuitos/1s/2020/03/05300.pdf>

| Annex point | Scope | Figure |
|---|---|---|
| 14 (RfG Art. 20(2)(a)) | Type B PPM | Fig. 10, identical to type C |
| 18 (Art. 21(3)(b)) | Type C/D PPM, U-Q at Pmax | Fig. 12 (U < 110 kV), Fig. 13 (type D, U ≥ 110 kV) |
| 19 (Art. 21(3)(c)) | Type C/D PPM, P-Q | Fig. 14 (U < 110 kV), Fig. 15 (U ≥ 110 kV) |
| 20 (Art. 25) | Offshore AC PPM | Figs 16/17 (not transcribed) |

Point 18.1 defines three voltage families: ≤ 60 kV, 150/220 kV, and 400 kV. Point 18.3 says that
with an OLTC, for U between 0.90 and 0.95 pu, 60 s is allowed to reach the required Q. Otherwise
the limit is < 10 s (18.4). The source sign convention is "consumo (capacitiva)" negative and
"produção (indutiva)" positive, which is the same orientation as ours.

**U-Q at Pmax: type B, and C/D with U < 110 kV (Figs 10 and 12).** The quadrilateral vertices are
printed on the figure: (−0.33, 0.95), (−0.33, 1.10), (+0.41, 1.05), (+0.41, 0.90).

| U (pu) | Q_min | Q_max |
|---|---|---|
| 0.90 | +0.41 (single point) | +0.41 |
| 0.95 | −0.33 | +0.41 |
| 1.00 | −0.33 | +0.41 |
| 1.05 | −0.33 | +0.41 |
| 1.10 | −0.33 | −0.33 (single point) |

Both slanted edges are linear: the bottom runs (−0.33, 0.95)→(+0.41, 0.90) and the top runs
(−0.33, 1.10)→(+0.41, 1.05).

**U-Q at Pmax: type D, U ≥ 110 kV (Fig. 13).** Coordinates were read from the gridded figure, so
confidence is Medium.

| U (pu) | Q_min | Q_max |
|---|---|---|
| 0.90 | 0 | +0.30 |
| 0.95 | −0.40 | +0.30 |
| 1.00 | −0.40 | +0.30 |
| 1.05 | −0.40 | +0.30 (upper limit at **400 kV**) |
| 1.10 (150/220 kV only) | −0.40 | +0.15, with a slope from (+0.30, 1.05) to (+0.15, 1.10) |

The lower-left edge is linear from (−0.40, 0.95) to (0, 0.90).

**P-Q (Figs 14 and 15).** Variant 1 applies to all PPMs. Variant 2 is a transitional option for
wind only, to be re-evaluated after ≥ 3 years.

| Case | P = 0 | 0 < P < 0.2 | P 0.2–1.0 |
|---|---|---|---|
| U < 110 kV, Variant 1 | −0.33 / +0.41 | −0.33 / +0.41 | −0.33 / +0.41 |
| U < 110 kV, Variant 2 (wind) | 0 / 0 | linear to −0.33 / +0.41 at 0.2 | −0.33 / +0.41 |
| U ≥ 110 kV, Variant 1 | −0.40 / +0.30 | −0.40 / +0.30 | −0.40 / +0.30 |
| U ≥ 110 kV, Variant 2 (wind) | 0 / 0 | linear to −0.40 / +0.30 at 0.2 | −0.40 / +0.30 |

So for PV the full rectangle applies down to P = 0.

**Storage.** The Portaria contains no storage provision; a search for "armazenamento" finds nothing.
Any storage rule (for example in later DGEG/REN acts) is **Unverified**.
**Type thresholds** (set in a separate act): **Unverified**.
**Amendments after 2020:** none were found, but no full check was made. Medium.

**Confidence: High** for type B/C and U < 110 kV, where vertices are printed. **Medium** for
type D ≥ 110 kV, which was read from the grid.

---

## 3. Poland

**Documents** (PSE, approved by the President of URE). Downloaded from the PSE package
<https://www.pse.pl/documents/20182/772549960/NCRfG_art_7_4_wymogi_ogolnego_stosowania.zip/b45f8987-c958-43de-a952-4b9100894d8b?safeargs=646f776e6c6f61643d74727565>,
which holds the PL and EN texts plus both decisions.

- **"Wymogi 2025"**: *Wymogi ogólnego stosowania wynikające z Rozporządzenia Komisji (UE) 2016/631
  (NC RfG) – Maj 2025 r.*, approved by decision DRE.WKP.744.18.15.2024.WŻ.MKo4 of 15 May 2025.
  **In force from 1 Dec 2025.** It applies to type B/C/D PGMs whose connection conditions are issued
  from 1 Dec 2025, and to type A from 1 Jan 2027. The PSE notice is at
  <https://www.pse.pl/-/zatwierdzenie-wymogow-ogolnego-stosowania-dla-przylaczania-jednostek-wytworczych>.
- **"Wymogi 2019"**: approved by decision DRE.WOSE.7128.550.2.2018.ZJ of 2 Jan 2019. It still
  governs PGMs not covered by Wymogi 2025.
- The IRiESP (transmission grid code) is **not** the source of the RfG PPM envelopes.

### Wymogi 2025 (current for new projects)

| Clause | Scope | Figure |
|---|---|---|
| Art. 20(2)(a) | Type B PPM, U-Q at Pmax | Fig. 11 (same shape as Fig. 16) |
| Art. 20(2)(a) | Type B PPM, P-Q | Fig. 12 (same shape as Fig. 17) |
| Art. 21(3)(b)(i) | Type D PPM, U-Q at Pmax; Table 16 inner envelope: 0.66 Q/Pmax width; voltage range 0.225 pu (400 kV and 220/110 kV) or 0.200 pu (< 110 kV) | Fig. 14 (400 kV), Fig. 15 (220/110 kV), Fig. 16 (< 110 kV) |
| Art. 21(3)(c)(i) | PPM P-Q; Table 17: max Q range 0.75 at all voltages | Fig. 17 |

**U-Q at Pmax.** Vertices are printed on the figures.

| U (pu) | 400 kV (Fig. 14) | 220/110 kV (Fig. 15) | < 110 kV and type B (Figs 16 and 11) |
|---|---|---|---|
| 0.875 | +0.165 / +0.33 | +0.165 / +0.33 | n/a |
| 0.90 | 0 / +0.33 | 0 / +0.33 | 0 / +0.33 |
| 0.95 | −0.33 / +0.33 | −0.33 / +0.33 | −0.33 / +0.33 |
| 1.00 | −0.33 / +0.33 | −0.33 / +0.33 | −0.33 / +0.33 |
| 1.05 | −0.33 / +0.33 (Q_max drops to 0 just above 1.05) | −0.33 / +0.33 | −0.33 / +0.33 |
| 1.10 | −0.33 / −0.24 | −0.33 / +0.10 | −0.33 / +0.10 |

Each cell is Q_min / Q_max. The polygons are:

- 400 kV: (−0.33, 1.10)–(−0.24, 1.10)–(0, 1.05)–(+0.33, 1.05)–(+0.33, 0.875)–(+0.165, 0.875)–(−0.33, 0.95).
- 220/110 kV: (−0.33, 1.10)–(+0.10, 1.10)–(+0.33, 1.05)–(+0.33, 0.875)–(+0.165, 0.875)–(−0.33, 0.95).
- < 110 kV and type B: (−0.33, 1.10)–(+0.10, 1.10)–(+0.33, 1.05)–(+0.33, 0.90)–(0, 0.90)–(−0.33, 0.95).
  Edges between the listed voltages are linear; use the polygon, not the table rows, for templates.

**P-Q (Fig. 17 for C/D at all voltages; Fig. 12 for type B)**

| P/Pmax | Q_min | Q_max |
|---|---|---|
| 0 – 0.1 | "all available reactive power per technical capability" (grey area); Q compensation at P = 0 required | same |
| 0.1 – 0.9 | **−0.35** | **+0.40** |
| 0.9 → 1.0 | linear −0.35 → −0.33 | linear +0.40 → +0.33 |
| 1.0 | −0.33 | +0.33 |

Above 1.05 pu the production limit follows the U-Q profile, and below 0.95 pu the consumption limit
does. Movement anywhere inside the P-Q profile must take ≤ 150 s, or ≤ 15 min with static
compensation.

### Wymogi 2019 (legacy)

- Type D ≥ 110 kV, U-Q: the same 400 kV and 220/110 kV polygons as above (its Fig. on p. 29).
- P-Q: −0.35 / +0.40 at P = 0.1, tapering linearly to (0, 0) at P = 0;
  −0.35 / +0.40 from 0.1 to 0.9; ±0.33 at 1.0.
- **Type B, and C/D < 110 kV: cos φ = 0.95 both directions at Pmax (±0.329)**, and not less than
  cos φ 0.95 at the actual P down to 0.1 Pmax. The 2025 text replaced this with the Fig. 16/11
  polygons.

**Storage.** Neither text mentions storage ("magazyn" or "storage" gives zero hits in Wymogi 2025).
**Unverified.**
**Type thresholds** (URE decision DRE.WOSE.7128.184.3.2018.ZJ: B ≥ 200 kW, C ≥ 10 MW, D ≥ 75 MW or
≥ 110 kV): **Unverified** in this pass.

**Confidence: High.** All vertices are printed on the figures.

---

## 4. France

**Documents**

- **Arrêté du 9 juin 2020** *relatif aux prescriptions techniques de conception et de fonctionnement
  pour le raccordement aux réseaux d'électricité*, JORFTEXT000042032189, in force 26 Jun 2020.
  Légifrance blocks automated access, so the text was read on the Pappers Justice mirror of the
  initial JO version:
  - **Art. 41**: RfG units on the **transmission network (RPT)**; applies RfG Art. 17(2)(a),
    18(2)(b,c), 20(2)(a), 21 and 25(5).
    <https://justice.pappers.fr/loi/JORFTEXT000042032189/article/JORFARTI000042032227>
  - **Art. 43**: RfG units on the **distribution network**.
    <https://justice.pappers.fr/loi/JORFTEXT000042032189/article/JORFARTI000042032229>
  - Art. 53: PPMs on the RPT must compensate the internal network when idle, if ΔU/Un > 0.5 %.
  - Art. 54: type A on HTA/BT (same 0.4/0.35 numbers as Art. 43).
- **RTE DTR Article 5.1.1**, *Exigences de conception et de fonctionnement pour le raccordement au
  RPT d'une unité de production*, **version 1.2 applicable from 03/08/2020**, §4.4.3 and Tableau 9.
  <https://services-rte.fr/files/live//sites/services-rte/files/documentsLibrary/Article%205.1.1%20-%20Exigences%20de%20conception%20et%20de%20fonctionnement%20pour%20le%20raccordement%20au%20RPT%20d%E2%80%99une%20unit%C3%A9%20de%20production_fr>
  A newer DTR version may exist; it was not checked.

**Transmission (RPT, Art. 41 + DTR 5.1.1 Tableau 9).** Udim is the design voltage, set per
connection: normally 405 kV for HTB3, 235 kV for HTB2, and the mean POC voltage for HTB1.

| Point | U | Q/Pmax at Pmax | Q/Pmax at any P > Pmin |
|---|---|---|---|
| A / A′ | Udim | **+0.32** | +0.30 |
| B | 0.9·Udim | +0.30 | +0.30 |
| C / C′ | Udim | **−0.35** | −0.28 |
| D / D′ | 1.1·Udim | < −0.35 | < −0.28 |

The minimum domain is trapezoid ABCD, truncated by the normal voltage-range limits of Art. 5.
RTE may shift the whole range upward by d, with 0 ≤ d ≤ +0.13 Pmax (Art. 41 IV). Below Pmax
(Art. 41 III), the range at Udim is [−0.28, +0.30] "whatever the active power".
This is the same rule for synchronous units and PPMs; the arrêté does not split them here.

**Distribution (Art. 43, RfG B/C/D on the public distribution network, e.g. HTA).**

- With U = Uc ± 5 % at Pmax, the unit must supply ≥ **+0.40·Pmax** or absorb ≥ **0.35·Pmax**,
  without time limit.
- From ±5 % to ±10 %, the unit follows the DSO DTR [U, Q] diagram. The Enedis diagram was
  **not retrieved (Unverified)**.
- The DSO sets the actual setpoint. A secondary source (photovoltaique.info) reports a fixed tan φ
  in a 0.1-wide band within [−0.35, +0.40] for HTA.

**P-Q below Pmax:** set only by Art. 41 III for the RPT. For distribution: **Unverified**.
**Storage:** no storage clause was found in the arrêté articles read or in DTR 5.1.1. **Unverified.**
**Type thresholds:** **Unverified.**

**Confidence: High** for the Art. 41 and Art. 43 numbers (text). **Medium** for the trapezoid
geometry (DTR v1.2, which may be superseded).

---

## 5. Croatia

**Document.** **Mrežna pravila prijenosnog sustava** (HOPS transmission grid code),
**NN 10/2024 (26 Jan 2024)**, čl. 145 (4.3.8.2) and **čl. 153 (4.3.12)**, Slike 8 and 9.
<https://narodne-novine.nn.hr/clanci/sluzbeni/2024_01_10_199.html>
The HOPS-hosted PDF rejected automated download.

- čl. 145(1): new and refurbished production modules at the POC must cover **Q/Pmax ≤ 0.33**,
  inductive or capacitive. Ranges beyond 0.33 are contracted as an ancillary service.
- čl. 153(4): the PPM controller must execute a Q/Pmax or voltage setpoint within 1 min, inside
  |Q/Pmax| ≤ 0.33.
- čl. 153(5–6): **type D PPM** P-Q (Slika 8) and U-Q (Slika 9).

**U-Q at Pmax (Slika 9, type D PPM):** a rectangle.

| U (pu) | Q_min | Q_max |
|---|---|---|
| 0.875 – 1.10 | **−0.33** | **+0.33** |

**P-Q (Slika 8, type D PPM).** Read from the figure, so confidence is Medium. Which side is
inductive is not labelled on the figure; this assumes the left side is negative/consumption.

| P/Pmax | Q_min | Q_max |
|---|---|---|
| 0.2 – 1.0 | −0.33 | +0.33 |
| 0.2 → 0.1 | linear −0.33 → −0.10 | +0.33 |
| 0.1 | −0.10 | +0.33 (the bottom edge runs from −0.10 to +0.10, then a vertical line at +0.33) |
| < 0.1 | not specified | not specified |

**Types B/C** (distribution, HEP ODS rules) and **storage**: **Unverified**. The transmission code
mentions storage only in the system-defence context (switching from load to generation).
**Thresholds:** a HOPS consultation proposal exists. **Unverified.**

**Confidence: High** for the ±0.33 rule and the U-Q rectangle. **Medium** for the P-Q low-power
corner.

---

## 6. Italy

**Documents** (Terna Codice di Rete; approved by ARERA Delibera 99/2023; applies to plants entering
service from 17 Mar 2023):

- **Allegato A.68**, *Centrali fotovoltaiche – Condizioni generali di connessione alle reti AT*,
  **Rev. 04, March 2023**, §8.3.1, Figs 4–7.
  <https://download.terna.it/terna/Allegato_A.68_versioni_precedenti_8deb1d6e6b2a971.pdf>
  The file name says "versioni precedenti", so a **newer revision may now be current. Not checked.**
- **Allegato A.79**, *Impianti con sistemi di accumulo elettrochimico – Condizioni generali di
  connessione alle reti AAT e AT*, **Rev. 00, March 2023**, §8.3, Figs 6–9.
  <https://download.terna.it/terna/Allegato_A.79_versioni_precedenti_8dd99f9df352674.pdf>
  A Terna consultation on revising A.79 has been reported (Qualenergia), so a newer revision may
  exist.
- ARERA/Terna approval notice:
  <https://download.terna.it/terna/Avviso%20Approvazione%20A,.17%20A.68%20A.79%20e%20capitolo%201C_8db29ebb2a52095.pdf>
- Scope: "Tipo 1" means connected at ≥ 110 kV, directly or indirectly. "Tipo 2" means connected
  to the 36 kV sections of RTN stations, with capability defined on the 36 kV side.
  **MV (type B on distribution) falls under CEI 0-16, which is paywalled: Unverified.**
- Terna's sign convention is +Q = capacitive (injection) and −Q = inductive (absorption). That is
  the same orientation as ours.

### PV (A.68 Rev. 04)

**P-Q (Fig. 4 Tipo 1; Fig. 6 Tipo 2), at P > 0.1 Pnd**

| | Absorption Q_min | Injection Q_max at Pnd |
|---|---|---|
| Tipo 1 (≥ 110 kV) | ≤ **−0.35** at every P | ≥ **+0.30** (+0.35 at Pnd with optional capacitor banks if Terna asks) |
| Tipo 2 (36 kV) | ≤ **−0.35** at every P | ≥ **+0.35** |

Below Pnd the limits follow the plant-specific semicircle, so the inner rectangle ±0.35 is the
binding minimum. Below 0.1 Pnd: either the inverter capability, or a progressive reduction to 0 at
P = 0.

**U-Q at Pnd (Fig. 5 Tipo 1; Fig. 7 Tipo 2)**

| U (pu) | Tipo 1 Q_min / Q_max | Tipo 2 Q_min / Q_max |
|---|---|---|
| 0.90 | 0 / +0.30 | 0 / +0.35 |
| 0.95 | −0.35 / +0.30 | −0.35 / +0.35 |
| 1.00 | −0.35 / +0.30 | −0.35 / +0.35 |
| 1.05 | −0.35 / +0.30 | −0.35 / +0.35 |
| 1.10 | −0.35 / 0 | −0.35 / 0 |

Both tapers are linear: Q_min from −0.35 at 0.95 to 0 at 0.90, and Q_max from its full value at
1.05 to 0 at 1.10. Outside ±10 % Vn, reductions are accepted.

### BESS (A.79 Rev. 00): storage-specific, with import mode explicit

- **At Pnd, in production *or* absorption**, the plant must cover the U-Q/Pnd envelope of
  Fig. 6 (Tipo 1) or Fig. 8 (Tipo 2). This has the same tapered shape as PV, with:
  - under-excited ≥ **−0.48 Pnd**;
  - over-excited ≥ **+0.30 Pnd** (Tipo 1) or **+0.40 Pnd** (Tipo 2);
  - total width ≥ **0.96 Pnd**. The envelope may be shifted horizontally for internal losses, as
    long as the minima above hold and Q = 0 stays reachable for 0.90–1.10 pu.
- **Below Pnd (|P| < Pnd), the P-Q is limited only by the inverter limits** (Fig. 7/9, a full
  circle-like envelope through both P+ and P−). At **P = 0** the plant needs ≥ **−0.90 Pnd** and
  ≥ **+0.72 Pnd** (Tipo 1) or **+0.82 Pnd** (Tipo 2), with total width ≥ **1.80 Pnd**.
- When the BESS sits in the MV section of a host plant (e.g. PV + BESS), the requirement applies
  to the BESS share alone at the POC, and may be shown by load flow.

**Confidence: High** for both annexes as read (values are printed). **Medium** on currency,
since newer revisions may exist.

---

## 7. Germany

**Documents.** Germany implements the RfG non-exhaustive requirements through the VDE FNN
technical connection rules (TAR). BNetzA does not publish separate envelope values. The standards
are paywalled; **none of the normative texts was read**. The values below come from VDE/FNN's own
summary slides and a certifier summary.

| Rule | Voltage level | Current edition | Next |
|---|---|---|---|
| VDE-AR-N 4110 (TAR Mittelspannung) | MV, 1 kV ≤ U < 60 kV | **4110:2023-09** | Novelle planned Dec 2026 (E VDE-AR-N 4110:2024-11 draft) |
| VDE-AR-N 4120 (TAR Hochspannung) | HV, 110 kV | 4120:2018-11 (no newer edition seen) | Novelle planned Dec 2026 |
| VDE-AR-N 4130 (TAR Höchstspannung) | EHV, 220/380 kV | 4130:2018-11 + A1:2026 (Jun 2026) | Novelle 2027 |

Source for editions: VDE planning sheet
<https://www.vde.com/resource/blob/2231082/c5692de0081519d6d7a6f5b393440d0f/geplante-voe-der-vde-tars-data.pdf>.
Confidence on editions: Medium.

**VDE-AR-N 4120 (HV), §10.2.2.2–10.2.2.3.** Source: VDE/FNN summary of draft E VDE-AR-N
4120:2017-05, Bild 4 and Bild 5.
<https://www.vde.com/resource/blob/1674518/0f43075f390bc86a0d51a74b805c683e/tar-hs-download-en-data.pdf>.
The IEA-PVPS 2024 report gives the same three variants.

The grid operator picks **one of three variants** at planning stage. Q is relative to Pb inst, the
installed active power available for operation. Westnetz's HV TAB names Variant 2 as its default,
per the search snippet; the Westnetz PDF itself was HTTP 403.

| Variant | Over-excited (production) at Pb inst | Under-excited (consumption) at Pb inst |
|---|---|---|
| 1 | **+0.48** (cos φ 0.90) | **−0.23** (cos φ 0.975) |
| 2 | **+0.41** (cos φ 0.925) | **−0.33** (cos φ 0.95) |
| 3 | **+0.33** (cos φ 0.95) | **−0.41** (cos φ 0.925) |

- U-Q (Bild 4, 110 kV level). The voltage band is 96–127 kV (0.873–1.155 of 110 kV). Each variant
  is a parallelogram: the full over-excited value holds from 96 to ≈ 120 kV, and the full
  under-excited value holds from ≈ 103 to 127 kV, joined by sloped edges. Medium (read from the
  figure).
- P-Q (Bild 5). The full range applies for P ≥ 0.2 Pb inst. It tapers linearly to about ±0.10 at
  0.05 Pb inst, read from the figure (Medium). Below 0.05 Pb inst there is no controlled Q, only
  ≤ 5 % of P_AV,E under-excited, and over-excited is not permitted.
- "Requirements apply equally to power generating modules, **storage**, and mixed facilities"
  (VDE summary, ch. 10). The rule for charging mode is **Unverified**.

**VDE-AR-N 4110 (MV), 2018 edition.** Source: M.O.E. GmbH summary, Windenergietage 2018.
<https://windenergietage.de/2018/wp-content/uploads/sites/3/2018/11/27WT07_F07_0945_4110_und_4120MOE_JM.pdf>.
This is a certifier summary, not the standard, and **the 2023-09 edition has not been checked**.

- **Q/Pb inst = 0.33 both directions (cos φ 0.95) at every operating point P > 0.2 Pn**, in
  "block" format. Active power may be reduced in favour of reactive power.
- U-Q band 0.90–1.10 Uc. Over-excited Q tapers from 0.33 at 1.075 Uc to 0 at 1.10 Uc.
  Under-excited Q tapers mirror-wise at low voltage. The slide labels the lower knee "1.075",
  which is apparently a typo for 0.925.
- Below 0.2 Pn: **Unverified.**

**VDE-AR-N 4130 (EHV):** **Unverified.** No envelope values were obtained.

**Confidence: Medium** for the 4120 variants (standard owner's summary of the 2017 draft).
**Low/Medium** for 4110 (certifier slide, 2018 edition). **Unverified** for 4130 and for the
storage charging-mode rule.

---

## 8. Comparison with Electrisim templates (`RPCDialog.js`, read-only)

Electrisim's sign convention, inferred from the template descriptions, is
q_max = over-excited (production) and q_min = under-excited. This matches ours.

### P-Q templates (`GRID_CODE_TEMPLATES`, lines 7–172)

| Template key | Claimed source | Verdict | Detail |
|---|---|---|---|
| `entsoe_ppm_inner` ("EU minimum", ±0.3287) | RfG Art. 21 | **Not traceable** | The RfG sets no minimum and no cos φ. Table 9 is a *maximum* width (0.75 Q/Pmax, CE) inside an outer box of −0.50…+0.65. |
| `entsoe_ppm_outer` ("max TSO range", +0.4108/−0.3287) | RfG Art. 21 | **Wrong** | The max range is 0.75 total width, positioned anywhere in −0.50…+0.65; it is not cos φ 0.925/0.95. |
| `vde_4120_v2` (+0.4108/−0.3287 at P ≥ 0.2) | VDE 4120 Var. 2 | **Matches at Pb inst** (Medium) | The low-P corner differs: VDE has about ±0.10 at 0.05 Pb inst and full range at 0.2; Electrisim has ±0.03/0.04 at 0.1. Variants 1 and 3 are missing. |
| `vde_4110` (±0.3287 at P ≥ 0.2) | VDE 4110 | **Matches 2018 summary** (Low/Medium) | Not checked against 4110:2023-09. The low-P rule is unverified. |
| `polish_iriesp_type_d` (+0.4843/−0.3287) | "IRiESP Type D" | **Not traceable** | No PSE RfG requirement found with cos φ 0.9/0.95. The PSE RfG source is the Wymogi, not IRiESP. |
| `polish_iriesp_ppm` (+0.4108/−0.3287) | "IRiESP PPM" | **Not traceable / superseded** | Wymogi 2019 gives ±0.329 (cos φ 0.95) only for type B and C/D < 110 kV. Wymogi 2025 replaces that with polygons. |
| `polish_iriesp_ppm_fig2_400kv` (−0.35/+0.40, ±0.33 at 1.0, taper to 0 at P = 0) | PSE Fig. 2 | **Matches Wymogi 2019** | The label "@ 400 kV" is too narrow: it applies to all ≥ 110 kV in 2019, and to all voltages and type B in 2025. For 2025, P < 0.1 is "technical capability" (grey), not a taper to 0. |
| `spanish_po122` (±0.3287 at P ≥ 0.2, ±0.033 at 0.1) | "P.O. 12.2 REE" | **Wrong source, close values** | The source is Orden TED/749/2020 Fig. 11: ±0.30 (not 0.3287) at P ≥ 0.2, ±0.15 at 0.1, ±0.05 below 0.1. |
| `italian_terna_a68` (+0.4843/−0.3287) | Terna A.68 | **Wrong** | A.68 Rev. 04 Tipo 1 is −0.35 / +0.30 (Tipo 2: ±0.35) for P > 0.1 Pnd. |
| `gb_grid_code`, `danish_energinet`, `sagc_*` | GB/DK/SA | Out of scope | Not among the target markets. |

### U-Q templates (`UQ_GRID_CODE_TEMPLATES`, lines 175–223)

| Template key | Verdict | Detail |
|---|---|---|
| `polish_iriesp_type_d_uq_400kv` | **Matches** PSE 2019 and 2025 Fig. 14 | Correct polygon, including the step to Q_max 0 just above 1.05 and −0.24 at 1.10. |
| `polish_iriesp_type_d_uq_110kv` (flat ±0.33, 0.875–1.10) | **Wrong for Poland** | PSE 220/110 kV (Fig. 15) tapers Q_max to +0.10 at 1.10 and lifts Q_min to +0.165 at 0.875. The flat rectangle is exactly **Croatia's** type D U-Q (NN 10/2024 Slika 9). |
| `entsoe_ppm_uq_inner` (flat ±0.3287, 0.9–1.1) | **Not traceable** | RfG sets no such minimum profile. |
| `PQ_TO_UQ_TEMPLATE` mapping | Partly wrong | `polish_iriesp_type_d` and `_ppm` map to the 110 kV rectangle, which inherits the error above. `vde_4110` maps to the "EU minimum" rectangle rather than the 4110 tapered profile. |

### Market coverage

| Market | P-Q present | U-Q present | Matches current primary source | Missing |
|---|---|---|---|---|
| Spain | Yes (mislabelled P.O. 12.2) | **No** | Approximate only | TED/749/2020 Fig. 11 exact P-Q; Fig. 10/12 U-Q parallelogram; storage mirrored into P < 0 |
| Portugal | **No** | **No** | n/a | All: type B and C/D < 110 kV (−0.33/+0.41, rectangle P-Q, quadrilateral U-Q); type D ≥ 110 kV (−0.40/+0.30) |
| Poland | Yes (1 of 3 traceable) | Yes (1 of 2 correct) | 400 kV U-Q and 2019 P-Q | Wymogi 2025 P-Q (grey < 0.1); 220/110 kV and < 110 kV / type B U-Q polygons |
| France | **No** | **No** | n/a | RPT Art. 41 / DTR Tab. 9 trapezoid; distribution Art. 43 (+0.40/−0.35 at Uc ± 5 %) |
| Croatia | **No** | Accidentally (the Polish "110 kV" template is the Croatian rectangle) | n/a | Type D P-Q (±0.33, taper to −0.10 at 0.1) and an explicitly labelled U-Q |
| Italy | Yes (wrong values) | **No** | No | A.68 Tipo 1/Tipo 2 P-Q and U-Q; **A.79 BESS** (−0.48/+0.30 or +0.40 at Pnd; P = 0 requirement; charging mode) |
| Germany | Yes (4110; 4120 Var. 2) | **No** (4110 maps to a generic rectangle) | At Pb inst, Medium | 4120 Var. 1 and 3; 4120 U-Q parallelograms; 4110 tapered U-Q; 4130; 4110:2023 recheck |

**Structural gap:** every Electrisim P-Q template has P ≥ 0 only. Two of the seven markets have a
verified explicit BESS import-mode rule: **Spain** (TED/82/2026, generator rules in absorption mode
with absorption Pmax) and **Italy** (A.79, P-Q through P−, plus a P = 0 requirement). Electrisim
has no way to express a negative-P (charging) half-envelope.

---

## 9. Open items (Unverified; do not template without a further check)

1. Germany: the normative 4110:2023-09, 4120:2018-11 and 4130:2018-11/A1:2026 texts (paywalled);
   the 4110 P-Q below 0.2 Pn; the storage charging-mode rule.
2. France: the current DTR 5.1.1 version; Enedis [U, Q] diagram for ±5–10 %; the storage rule;
   type thresholds.
3. Italy: whether A.68 Rev. 05 or A.79 Rev. 01 has replaced the versions read; CEI 0-16 for MV
   type B.
4. Portugal: type thresholds; any storage act; amendments after 2020.
5. Croatia: HEP ODS distribution rules for type B/C; storage.
6. Type thresholds for Spain and Poland, which were quoted from memory and not re-read.

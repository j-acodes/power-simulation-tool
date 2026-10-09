# Research: does ambient temperature change a containerised LFP battery's DC efficiency?

Answers ticket [02-dc-efficiency-vs-ambient](../issues/02-dc-efficiency-vs-ambient.md) for the
[efficiency-run map](../map.md). Terms follow `CONTEXT.md` (**Efficiency run**, **Auxiliary
consumption**, **BESS solution**). Researched 2026-10-09.

## Answer

In a thermally managed container, ambient temperature has only a small, indirect effect on
DC-side round-trip efficiency, as long as the thermal system holds the cells in their band. The
ambient effect on RTE at the point of connection is carried mostly by **auxiliary consumption**:
cooling in hot weather, heating in cold weather. DC efficiency depends on cell temperature, not
ambient temperature. Cell temperature in a liquid-cooled container is set mainly by the coolant
setpoint and by the cells' own heating at the cycle's C-rate. Within a typical regulated band
(about 20–35 °C), LFP cell resistance changes by only a few tenths of a percent per kelvin. For a
cell that loses a few percent per cycle, that moves DC RTE by roughly 0.1–0.3 percentage points
across the band. That is an order of magnitude below the seasonal swing in auxiliary
consumption measured in the field. The DC effect becomes material only when cells run cold
(below about 15 °C, where charge-transfer resistance climbs steeply) or when the thermal system
reaches its limit. A manufacturer signals that hot limit through PCS/system derating
(PowerTitan 2.0 derates above 45 °C), and the efficiency run already models derating through
the derated power.

Confidence: **medium**. The mechanism and direction are well supported. The magnitude for
modern liquid-cooled LFP containers is an inference from cell-level resistance data and older
field data, because no primary source publishes a DC-RTE-versus-ambient curve for this class
of product.

## Evidence

### 1. Manufacturer documents publish no DC curve and no RTE conditions

- The Sungrow PowerTitan 2.0 (ST5015UX-2H/-4H-US) datasheet lists LFP 3.2 V/314 Ah cells
  (416S12P, 5015 kWh), "Intelligent Liquid Cooling", and an operating range of −30 to 50 °C
  "(> 45 °C Derating)". It gives no DC or system RTE, no auxiliary power figure, and no
  cell-temperature band. Its only thermal claim is qualitative: an "intelligent liquid-cooled
  temperature control system to optimize the auxiliary power consumption".
  [datasheet PDF](https://info-support.sungrowpower.com/datasheet-materials/1a38db5b-a599-43d3-ac10-dfe06dee5d2a.pdf),
  [product page](https://www.sungrowpower.com/us/en/products/energy-storage-systems/powertitan-20-st5015ux-2h-us-st5015ux-4h-us)
- The 6-hour variant's page claims "no derating up to 55 °C". That claim is the thermal
  system's capacity limit, expressed as power derating, not as an efficiency change.
  [B-ST5015UX-6H page](https://sungrowpower.com/en/products/utility-energy-storage-system/b-st5015ux-6h)
- Implication: for this product class, the realistic input is a single DC efficiency (if the
  manufacturer gives one at reference conditions) plus an auxiliary-consumption curve. A DC
  curve against ambient temperature is not on offer.

### 2. Standards and test protocols treat auxiliary consumption as separate from RTE

- IEC 62933-2-1:2017 has separate parameters and tests for *roundtrip efficiency* (5.2.3,
  6.2.3) and *auxiliary power consumption* (5.2.6, 6.2.6).
  [VDE preview, table of contents](https://assets.vde-verlag.de/iec-normen/preview-pdf/info_iec62933-2-1%7Bed1.0%7Db.pdf).
  The clause text, including the ambient conditions, is paywalled and was not read.
- The DOE/PNNL/Sandia *Protocol for Uniformly Measuring and Expressing the Performance of
  Energy Storage Systems* (PNNL-22010 Rev 2, 2016) defines RTE as discharge energy over charge
  energy. It gives separate equations for when the system powers its own auxiliary loads and
  for when auxiliaries are fed separately. The separate-feed case is the efficiency run's
  arrangement: auxiliaries fed from the MV busbar, with discharge, charge and rest auxiliary
  energy (AuxD, AuxC, AuxR) assigned explicitly. The protocol records ambient temperature as a
  test condition but does not prescribe a temperature correction.
  [PNNL-22010 Rev 2](https://www.sandia.gov/app/uploads/sites/163/2023/03/PNNL-22010Rev2.pdf)

### 3. Field data: the seasonal effect appears in auxiliary consumption

PNNL's assessment of the SnoPUD MESA-1 system (2 MW / 1 MWh, Everett WA; Mitsubishi/GS Yuasa
and LG Chem banks, so **not LFP and not liquid-cooled**) is the most detailed public field
dataset that separates the two effects.
[PNNL-27237 (2018)](https://www.pnnl.gov/main/publications/external/technical_reports/PNNL-27237.pdf)

- Grid RTE ranged from 66 to 91 % depending on power, rest periods and auxiliary consumption
  (Executive Summary, Outcome 1). The C/4 RTE was lowest in the baseline tests "because of
  higher auxiliary power consumption during summer".
- Excluding auxiliary consumption raised RTE by 6–16 points. Excluding it only during rest
  periods raised RTE by 3–5 points, and the gain was largest in the summer tests.
- Auxiliary consumption was about 30 kW at the C rate. It was 5–7 kW lower in the cooler-weather
  test campaigns, at all C-rates and in both charge and discharge (§2, Fig. 2.36; regression in
  Table 2.18, p < 1e-8). The conclusions state: "Auxiliary power consumption decreases during
  winter – less cooling needed" and "increases with increasing charge or discharge power".
- Battery temperatures stayed "in a tight band" across seasons, while the hotter ambient
  "requires greater auxiliary cooling power" (§2, Fig. 2.46 discussion). For one winter run the
  battery operated at 17–27.5 °C, with about 2.5 °C spread.
- With auxiliary consumption excluded (a DC-plus-PCS figure), RTE was 83 % at C/4, about 88 %
  at C/2, 91 % at 1C and 88 % at 2C. PNNL attributes the low-rate shortfall to cell
  temperature: "At lower rates, the temperature is low, while at high rates, the polarization
  losses are higher in spite of higher operating temperature" (§2.1). Cell temperature therefore
  does affect DC efficiency, but in this dataset C-rate, through self-heating, drives cell
  temperature more than ambient does.
- Caution: one 2C run was excluded because it started 3.5 °C colder and showed about 8 points
  lower RTE. That figure *includes* auxiliary consumption and rest, so it is not a clean DC
  sensitivity.

### 4. System modelling: thermal management sets cell temperature, and auxiliaries dominate at low utilisation

Schimpe et al. (2018), with NREL co-authors, built an electro-thermal model of a 192 kWh LFP
container, validated against measurements.
[Applied Energy 210:211–229, accepted manuscript on OSTI](https://www.osti.gov/servlets/purl/1409737)
([record](https://www.osti.gov/biblio/1409737))

- The battery-zone air setpoint is 15 °C (target range 10–20 °C). Because Berlin's mean ambient
  is 8.9 °C, the thermal-management consumption stayed small and outdoor air could cool the
  system most of the time.
- Conversion efficiency peaked when continuous cycling raised battery temperature: "This leads
  to decreasing cell resistances and thus higher battery efficiencies". This is self-heating,
  not ambient. Varying the average SOC changed conversion efficiency by less than 1 point.
- Auxiliary (system) consumption cut overall efficiency by 8–13 points for the PCR and PV-battery
  profiles, against a conversion RTE of about 70–80 %.

### 5. Cell-level physics: resistance against temperature for LFP

- Wu et al. (2021) ran EIS on 40 Ah prismatic LFP cells at 100 % SOC (Table 2). Ohmic R was
  4.92 / 4.65 / 4.40 / 4.17 mΩ and charge-transfer Rct was 34.1 / 7.47 / 4.61 / 4.24 mΩ, at
  −20 / 5 / 25 / 45 °C. R + Rct is therefore about 9.0 mΩ at 25 °C and 8.4 mΩ at 45 °C, a 6.5 %
  drop over 20 K (about 0.3 %/K). It is about 12.1 mΩ at 5 °C, 35 % higher than at 25 °C. The
  authors name 20–30 °C as the best operating temperature.
  [IOP Conf. Ser.: EES 675 012220 (open access)](https://iopscience.iop.org/article/10.1088/1755-1315/675/1/012220/pdf)
- Sandia's multi-year study cycled A123 LFP 18650s at 15, 25 and 35 °C with 0.5C charge and
  0.5–3C discharge. It finds that "RTE depends substantially on the cycling conditions,
  including the charge/discharge rate, temperature, SOC, and rest time"; that LFP cells "show
  higher RTEs than NCA and NMC cells at all conditions"; and that "RTE consistently decreased
  with increasing discharge rate". The per-temperature values exist only as a figure (Fig. 2c)
  and in raw data on batteryarchive.org, which this research did not reprocess. Preger et al.,
  J. Electrochem. Soc. 167 120532 (2020).
  [paper](https://iopscience.iop.org/article/10.1149/1945-7111/abae37)

## Magnitudes and the conditions they hold under

| Effect | Magnitude | Holds under | Source |
|---|---|---|---|
| Seasonal auxiliary swing | 5–7 kW on ~30 kW (1 MWh system); RTE impact several points, largest at low C-rate and with rest | Air-conditioned, non-LFP, 1 MW/1 MWh, C/4–2C, 7.5–92.5 % SOC | PNNL-27237 |
| Auxiliary share of total loss | 8–13 points of overall efficiency (PCR, PV-battery) | Modelled 192 kWh LFP, air-cooled, Berlin climate | Schimpe 2018 |
| LFP resistance vs cell temperature, 25→45 °C | about −0.3 %/K (R + Rct, EIS) | 40 Ah prismatic, 100 % SOC | Wu 2021 |
| LFP resistance vs cell temperature, 25→5 °C | +35 % over 20 K; steepening below about 15 °C | Same | Wu 2021 |
| Implied DC RTE change across a 20–35 °C cell band | about 0.1–0.3 points (inference: polarisation loss scales with resistance at fixed current; assumes a cell DC loss of about 3–6 % per cycle at 0.25–0.5C) | Cells held in band; C-rate ≤ 0.5C; middle-to-wide SOC window | Derived from Wu 2021; not directly measured |
| C-rate effect on DC (+PCS) RTE | 83 % at C/4 to 91 % at 1C (aux excluded) | Non-LFP field system; partly a self-heating effect | PNNL-27237 |
| SOC-window effect | < 1 point | Modelled LFP, average SOC varied 20–80 % | Schimpe 2018 |

## What this implies for the efficiency run

**Recommended default treatment (when the manufacturer publishes no DC curve):**

1. **Treat DC round-trip efficiency as independent of ambient.** Use one value per BESS
   solution at the run's C-rate (the declared discharge duration). Take it from the
   manufacturer's DC or battery RTE at its stated reference conditions (typically 25 °C at
   0.5P or the rated P). If none is published, take it as a typed-in parameter. Record the
   reference C-rate with the value.
2. **Put all ambient dependence into auxiliary consumption**, as an operating/idle curve against
   ambient, consistent with the map's framing and with PNNL-22010's separate-feed RTE equation.
   This is where the measurable effect lives.
3. **Leave the hot-ambient DC effect to PCS derating.** Above the derating threshold (45 °C for
   PowerTitan 2.0), the run already uses derated power, so the C-rate falls. A lower C-rate
   *raises* DC efficiency slightly (less I²R loss). Ignoring that keeps the run conservative.
4. **Flag rather than model the cold edge.** Below about 15 °C *cell* temperature, DC losses
   rise steeply, but a managed container heats its cells, and that heating appears as auxiliary
   consumption. Do not add a DC penalty for cold ambient by default. If an ambient falls
   outside the product's stated operating range (−30 °C for PowerTitan 2.0), the run should
   warn, which ties into the map's "ambients outside the curves' range" item.
5. **If a manufacturer *does* publish DC efficiency against temperature**, the curve's x-axis is
   almost certainly cell or coolant temperature, not ambient. Using it would need a thermal
   model to map ambient to cell temperature, which is out of proportion to a 0.1–0.3 point
   effect. Prefer the single reference value unless a curve is explicitly against ambient.

**Size of the error accepted by this simplification:** a few tenths of a point of DC RTE inside
the regulated band. That is small next to the auxiliary-consumption swing and next to the
uncertainty in the C-rate and the loss chain.

## Gaps and caveats

- No primary source was found with measured DC RTE against *ambient* for a modern liquid-cooled
  LFP container (PowerTitan, CATL EnerC/TENER, Tesla Megapack and similar). Manufacturers do not
  publish one, and the public field reports (MESA-1) cover older, air-conditioned, non-LFP
  systems.
- The 0.1–0.3 point band is an inference from EIS resistance on a 40 Ah cell. EIS R + Rct
  understates the full DC resistance because it omits diffusion, and modern 280–314 Ah cells
  have much lower absolute resistance. The relative temperature coefficient is assumed to carry
  over.
- The IEC 62933-2-1 clause text, including its ambient conditions and whether its RTE includes
  auxiliaries, is paywalled and was not read. Only the table of contents was verified.
- Sandia's per-temperature LFP RTE values (15/25/35 °C) are available only as a figure and as
  raw data. Reprocessing the batteryarchive.org files would give a direct cell-level check of
  the 0.1–0.3 point estimate.
- Not used as evidence because it is secondary: a KTH master's thesis
  ([Carel 2025](https://www.diva-portal.org/smash/get/diva2:1957602/FULLTEXT01.pdf)) simulating a
  liquid-cooled 4 MWh LFP system found overall efficiency differing by under 0.5 points between
  Stockholm, St Etienne and Madrid (87.64 / 87.54 / 87.17 %), driven by cooling demand. This is
  consistent with the conclusion above. Vendor blogs quoting 1.5–2.5 % cooling parasitics were
  likewise not used.

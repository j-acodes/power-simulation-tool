# 03: Make inverter capacity govern PV solving

**What to build:** A sizing engineer's PV operating point is allocated and checked against the
installed inverter fleet rather than inferred from transformer rating. The requested POC active
power and power factor still govern delivery; the refined inverter-side P/Q duty is shared between
stations in proportion to each station's ambient-rated inverter capacity. Active, apparent and
minimum-power-factor violations produce prominent warnings while retaining calculated results.
Transformer loading remains an independent check against the transformer station.

**Blocked by:** 02: Configure a Sungrow inverter inside a PV station.

**Status:** done

- [x] Per-unit inverter power resolves explicitly at 30 °C and 40 °C with no interpolation
- [x] SG350HX-20 resolves to 352 kW/kVA at 30 °C and 320 kW/kVA at 40 °C
- [x] Missing 30 °C power falls back to 40 °C with an explicit notice
- [x] Mixed PV stations receive P/Q shares proportional to installed inverter power
- [x] Per-station active and apparent limits are checked independently
- [x] Inverter-side PF below a published minimum produces a warning
- [x] Capacity/PF violations return results and do not become solve errors
- [x] Transformer losses/loading still use allocated station duty and the transformer loading limit
- [x] Inverter capacity always uses 100% of its ambient rating
- [x] POC target, shared export equipment, hybrid reactive split and BESS behavior are unchanged
- [x] Domain documentation records inverter ambient power and explicit engineering provenance
- [x] Focused diagram-solve tests pass for PV-only, mixed-station and active hybrid cases
- [x] Full affected Python type/static checks pass

# 03: Make inverter capacity govern PV solving

**What to build:** A sizing engineer's PV operating point is allocated and checked against the
installed inverter fleet rather than inferred from transformer rating. The requested POC active
power and power factor still govern delivery; the refined inverter-side P/Q duty is shared between
stations in proportion to each station's ambient-rated inverter capacity. Active, apparent and
minimum-power-factor violations produce prominent warnings while retaining calculated results.
Transformer loading remains an independent check against the transformer station.

**Blocked by:** 02: Configure a Sungrow inverter inside a PV station.

**Status:** ready-for-agent

- [ ] Per-unit inverter power resolves explicitly at 30 °C and 40 °C with no interpolation
- [ ] SG350HX-20 resolves to 352 kW/kVA at 30 °C and 320 kW/kVA at 40 °C
- [ ] Missing 30 °C power falls back to 40 °C with an explicit notice
- [ ] Mixed PV stations receive P/Q shares proportional to installed inverter power
- [ ] Per-station active and apparent limits are checked independently
- [ ] Inverter-side PF below a published minimum produces a warning
- [ ] Capacity/PF violations return results and do not become solve errors
- [ ] Transformer losses/loading still use allocated station duty and the transformer loading limit
- [ ] Inverter capacity always uses 100% of its ambient rating
- [ ] POC target, shared export equipment, hybrid reactive split and BESS behavior are unchanged
- [ ] Domain documentation records inverter ambient power and explicit engineering provenance
- [ ] Focused diagram-solve tests pass for PV-only, mixed-station and active hybrid cases
- [ ] Full affected Python type/static checks pass

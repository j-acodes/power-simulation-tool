# 04: Generate and customize inverter-based PV stations

**What to build:** A sizing engineer creating a PV layout selects a PV Transformer Station, a
paired inverter and the number of inverters per station; setup then derives the station quantity
needed to carry both active and apparent conversion duty. After generation, each station can be
edited independently. A custom station can carry a one-off custom inverter with enough explicit
data to participate in the same sizing and warning behavior without becoming a catalogue product.

**Blocked by:** 03: Make inverter capacity govern PV solving.

**Status:** ready-for-agent

- [ ] PV setup selects station, paired inverter and bounded count in that order
- [ ] Count defaults to the pairing maximum
- [ ] Generated station quantity is sufficient for both loss-adjusted active and apparent inverter duty
- [ ] Transformer loading is reported separately and does not determine inverter-based station quantity
- [ ] Generated stations persist the selected inverter and count and can diverge after individual edits
- [ ] Custom inverter requires name, 40 °C power, nominal AC voltage and positive integer count
- [ ] Custom 30 °C power and minimum PF are optional
- [ ] Missing custom 30 °C power uses 40 °C power and returns a notice
- [ ] Catalogue and custom voltage are stored/displayed but never validated
- [ ] Custom inverter values do not create reusable catalogue entries or supplier specification views
- [ ] Seed/API/diagram and focused setup/inspector tests pass
- [ ] Python and frontend typechecking pass

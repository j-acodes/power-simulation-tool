# 04: Generate and customize inverter-based PV stations

**What to build:** A sizing engineer creating a PV layout selects a PV Transformer Station, a
paired inverter and the number of inverters per station; setup then derives the station quantity
needed to carry both active and apparent conversion duty. After generation, each station can be
edited independently. A custom station can carry a one-off custom inverter with enough explicit
data to participate in the same sizing and warning behavior without becoming a catalogue product.

**Blocked by:** 03: Make inverter capacity govern PV solving.

**Status:** done

- [x] PV setup selects station, paired inverter and bounded count in that order
- [x] Count defaults to the pairing maximum
- [x] Generated station quantity is sufficient for both loss-adjusted active and apparent inverter duty
- [x] Transformer loading is reported separately and does not determine inverter-based station quantity
- [x] Generated stations persist the selected inverter and count and can diverge after individual edits
- [x] Custom inverter requires name, 40 °C power, nominal AC voltage and positive integer count
- [x] Custom 30 °C power and minimum PF are optional
- [x] Missing custom 30 °C power uses 40 °C power and returns a notice
- [x] Catalogue and custom voltage are stored/displayed but never validated
- [x] Custom inverter values do not create reusable catalogue entries or supplier specification views
- [x] Seed/API/diagram and focused setup/inspector tests pass
- [x] Python and frontend typechecking pass

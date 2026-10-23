# 13: Idle loss column

**What to build:** The `idle loss %` column becomes real for runs without a design: standby
container auxiliary consumption × containers, plus standby MVS auxiliary consumption ×
stations, plus the typed no-load loss, divided by the fleet's nominal energy, in % per hour,
as energy imported at the POC. See [spec](../spec.md), "The idle figure", and
[ticket 10](10-idle-figure.md).

**Blocked by:** 12

**Status:** ready-for-agent

- [ ] The worked example's idle loss at 25 °C reproduces: 0.094 %/h (417 kW over 441.9 MWh).
- [ ] The idle figure does not change with derating, and carries no load losses.
- [ ] Out-of-range ambients clamp the same way as the operating figure.

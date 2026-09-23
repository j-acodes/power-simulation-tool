# PV inverter power governs conversion capacity and may carry declared engineering provenance

A PV station's transformer station and inverter fleet answer different questions. The
transformer station carries an allocated operating point and is checked against its own
ambient-rated apparent power and the design's transformer loading limit. The installed
inverters establish how much active and apparent power the station can convert. PV duty is
therefore allocated between stations in proportion to inverter count times per-unit inverter
power at the design ambient, not in proportion to transformer-station rating.

One inverter power figure at an ambient is both its active limit in kW and apparent limit in
kVA. This is the project's explicit power-factor-1 interpretation of the catalogue figure.
The limits remain two separate checks because an operating point can pass active capacity and
fail apparent capacity. Inverter-side power factor is also checked against the product's
published minimum. All three failures are warnings: the electrical result remains available.

## Ambient lookup

The catalogue stores a required 40 °C power and an optional 30 °C power. Lookup is exact and
never interpolates. A missing 30 °C figure falls back to the 40 °C figure and produces a notice.
The SG350HX-20 uses 352 kW/kVA at 30 °C and 320 kW/kVA at 40 °C.

## Provenance

Simulation values normally come from supplier literature. An owner-declared engineering value
may supplement or override that literature only when its non-supplier provenance is explicit in
the catalogue and specification view. It must not be presented as a supplier temperature claim.
Under that rule, the agreed Huawei SUN2000-330KTL-H1 simulation basis is 330 kW/kVA at 30 °C and
300 kW/kVA at 40 °C, while the typed supplier fields continue to reproduce Huawei's own labels.

## Consequences

Adding inverter nameplate does not change the requested POC operating point. The existing
backward loss cascade still resolves the conversion-side P and Q needed to deliver that target;
only station allocation and compliance authority move to the installed inverter fleet.
Transformer losses and loading are then calculated from each station's allocated duty. The PV
transformer loading percentage never derates inverter capacity: inverter checks always use 100%
of the resolved ambient power.

BESS allocation and compliance were unchanged by this record; ADR-0008 later applies the same rule to the PCS. An inverter remains contained by a station and is
not a separately connected diagram node.

# Does ambient temperature change a containerised battery's DC efficiency?

**Type:** research
**Status:** resolved
**Blocked by:** None

## Question

In a thermally managed, containerised LFP BESS (e.g. Sungrow PowerTitan class), does ambient
temperature materially change the DC-side round-trip efficiency, or is the ambient effect on
RTE carried almost entirely by auxiliary consumption (HVAC) while cell temperature is held in
band? Survey manufacturer documents, application notes and published field/test data. Report
magnitudes, the conditions they hold under (cell temperature band, C-rate, SOC window), and
what this implies for the efficiency run when a manufacturer publishes no DC curve.

## Answer

Barely, while cells are held in band. DC efficiency follows cell temperature (set by the
coolant setpoint and C-rate self-heating), not ambient; the inferred DC RTE swing across a
~20–35 °C cell band is ~0.1–0.3 points. The ambient effect on RTE at the POC is carried almost
entirely by auxiliary consumption (field data: leaving it out shifted RTE by 6–16 points).
DC losses become material only for cold cells (< ~15 °C) or at the hot thermal limit, which
shows up as PCS/system derating.

Default for the efficiency run when no DC curve is published: one ambient-independent DC RTE
per BESS solution (manufacturer figure at its reference conditions, else typed in); all
ambient dependence in the auxiliary-consumption curve; hot ambients via derating; no default
cold penalty, but warn outside the product's operating range. A published DC curve is almost
certainly against cell/coolant temperature, not ambient: check its axis.

Confidence: medium (mechanism well sourced; magnitude for modern liquid-cooled LFP inferred).

Findings, with citations: `.scratch/rte-efficiency/research/dc-efficiency-vs-ambient.md` on
branch `research/dc-efficiency-vs-ambient` (commit 5042678).

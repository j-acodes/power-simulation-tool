# How does cycles per day enter the efficiency run?

**Type:** grilling
**Status:** open
**Blocked by:** None

## Question

Sungrow publishes auxiliary consumption for PowerTitan 3.0 at a reference of 1 and of
2 cycles/day, and the figures differ (notably standby at 15–45 °C). The efficiency run is
evaluated per timestamp and does not know the dispatch. Is cycles per day a fixed project
parameter that selects the table, an input per run (interpolating or stepping between 1 and
2), or is one table chosen and the other ignored? What happens for a solution that publishes
only one reference? Also settle what "operating power" and "standby power" mean: average
draw over the time spent in that state, per container.

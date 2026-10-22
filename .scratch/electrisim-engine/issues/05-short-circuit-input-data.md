# Where do short-circuit inputs come from?

**Type:** grilling
**Status:** claimed
**Blocked by:** None

## Question

IEC 60909 and the POI fault study need inputs the catalogues lack: inverter and PCS fault
current contribution (Ik" or k factor, per fault type), transformer vector group and
zero-sequence impedance (and neutral earthing), numeric switchgear short-time withstand
and peak ratings (today a text string such as "IAC AFL 20 kA / 1 s"), and the grid's
short-circuit power and X/R at the POC (Sk max/min).

For each: is it a simulated catalogue parameter transcribed from datasheets, a project
input typed per design, or a default (e.g. IEC 60909 k = 1.1–1.2 for converters) flagged
as a project assumption like the existing ones? Which are blocking for a first check and
which can start as defaults?

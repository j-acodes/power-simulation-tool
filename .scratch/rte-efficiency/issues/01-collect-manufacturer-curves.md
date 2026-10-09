# Collect the manufacturer curves

**Type:** task (HITL)
**Status:** open
**Blocked by:** None

## Question

Which manufacturer curves do we actually have for the target BESS solution(s)? Gather the files
into `data/manufacturer-curves/<supplier>/` (any format: PDF, XLSX, CSV, images). At minimum
look for:

- auxiliary consumption vs ambient temperature, operating and idle
- PCS power derating vs ambient temperature
- PCS efficiency (at rated power, or vs load)
- DC / battery round-trip efficiency, if published (vs temperature, C-rate or SOC)

Resolved when the files are in the repo; the answer records what each file contains (axes,
units, operating points, which product and model number it covers) and what is missing.

# A transformer station's rating is stored per ambient temperature, and never interpolated

A transformer station's apparent power depends on the ambient temperature it is rated at, and
suppliers do not say so: Sungrow's MVS datasheets publish one kVA figure with no temperature
against it, and TBEA publishes two without naming a field for either. The catalogue therefore
holds an explicit rating per ambient — `s_rated_kva_at_40c`, required, and
`s_rated_kva_at_30c`, nullable and unpopulated today — rather than one rating plus a derating
rule. A design that asks for an ambient an entry does not publish is warned and falls back to
the nearest published rating at or below it.

## Considered Options

**A rating map keyed by ambient** (`{30: null, 40: 7080, 50: 6400}`) was the same effort and
would have preserved TBEA's published 50 °C figures, which today survive only as comments in
`data/transformers.yaml` and will be lost. Two fixed fields were chosen instead because 30 and
40 °C are the two temperatures this project actually designs to, and a map invites the
interpolation the next paragraph exists to forbid. The 50 °C figures get re-transcribed if and
when a derating curve arrives.

**A derating curve or coefficient** was rejected outright: no datasheet in `data/datasheets`
publishes one, so any curve would be invented, and an invented curve is indistinguishable from
a measured one once it is in the file.

## Consequences

**Lookup only.** A rating that is not published is not computed. This is the same stance the
project already takes for discharge duration, where the ST6900UX-4H sells 4 h although its
energy over its PCS rating works out to 3.84 h — the nameplate is what gets procured, so the
nameplate is what the catalogue records.

**The fallback understates the station, deliberately.** Falling back from an unpublished 30 °C
to the published 40 °C figure sizes the plant with less power than the station really has at
30 °C. That direction is safe; the reverse is not.

**Every entry in both catalogues gains a temperature it never declared.** The existing PV
entries in `data/transformers.yaml` are annotated `@40C` in comments, and that comment is the
only evidence for the value moving into `s_rated_kva_at_40c`. It is trusted rather than
re-derived, because no datasheet states it either.

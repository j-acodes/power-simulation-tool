# Switchgear rated current bounds a circuit; the flat planning cap is retired

An MV collector circuit used to be bounded by `max_circuit_current_a`, a flat 400 A setting
inherited from the deleted Streamlit sidebar. It was not derived from any equipment: it applied
to every design at every voltage regardless of what was drawn, and it was checked only against
the trunk segment. Meanwhile the figure that really bounds a circuit — the rated current of the
MV switchgear inside each transformer station — sat in the catalogue as a typed parameter,
transcribed but never read.

We retired the flat cap and promoted `rmu_rated_current_a` to the simulated tier. A circuit is
now bounded by the switchgear of the stations in it, checked per station against that station's
**through current**: its own current plus that of every station downstream of it in the chain.
This is the first figure outside the transformer itself that the sizing engine reads from a
transformer station, which is a deliberate widening of what the enclosure contributes to a
design.

## Considered options

Keeping the flat cap alongside the switchgear limit was considered and rejected by the owner: a
company-standard current cap is a real thing, but it was not what this setting was, and keeping
a guessed default beside a published figure invites the guess to be mistaken for the fact. The
setting is deleted outright — field, default, UI control and `settings.rules` entry — following
the precedent set when `default_count` was deleted rather than retained once it had no reader.

## No utilization factor

Cables are held to `max_utilization` (0.80) because their catalogue ampacity assumes an
installation condition — direct in ground, single circuit, soil ~1.0 K·m/W — that a real trench
rarely matches. Switchgear carries no equivalent variance: a rated current is a continuous
thermal rating inside its own enclosure. Reusing the cable factor would silently derate every
station by 20% for a reason that does not apply, so the switchgear rating is a hard limit. A
margin setting can be added when a reason to want one appears; it is not invented here.

## Unpublished ratings fall back, never to unlimited

Suppliers do not all publish this figure. Sungrow does (630 A, for both the PV MVS stations and
the MVS7400-LS / MVS7080-LS); Huawei publishes switchgear units, relay protection and
short-time withstand for the JUPITER stations but no rated current. An unpublished rating falls
back to **630 A**, the standard IEC ring-main-unit size, and says so in a notice — the same
stance ADR-0004 takes for an unpublished ambient and the catalogue takes for an unpublished
auxiliary consumption: understate or default in the safe direction, declare it, never invent
silently and never treat silence as the absence of a limit. The fallback lives in the engine and
deliberately not in the YAML, so that writing 630 A into a station's datasheet block always
means a supplier published it.

## Consequences

Circuits get materially larger: at 20 kV the bound moves from 400 A (~13.9 MVA) to 630 A
(~21.8 MVA), so designs resolve to fewer, heavier circuits. Cable ampacity does not restrain
this — the largest MV cable in the catalogue is 600 A and `select_cable` adds parallel runs
rather than refusing — so trunk segments commonly go to two parallel cables. Every existing
design's numbers move, and the golden baseline moves with them.

The two failure modes are deliberately different. A station whose own current alone exceeds its
own switchgear rating is a hard error: the catalogue contradicts itself and no number downstream
of it is trustworthy. A circuit that is collectively too heavy is a compliance failure that
still solves and still reports its currents, because the engineer needs to see those currents to
know where to split the circuit. Stage-1 planning may order stations to satisfy the limit; a
drawn diagram is never silently rearranged.

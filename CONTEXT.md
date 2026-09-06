# Power Simulation Tool

A sizing tool for the electrical plant between a renewable generation asset and its grid
connection: an engineer draws the plant as a single-line diagram, and the tool works
backward from the power required at the grid to the equipment needed to deliver it.

## Language

**Point of connection (POC)**:
The single point where the plant meets the grid. Every sizing calculation works backward
from a power figure set here. A design has exactly one POC, regardless of how many kinds of
generation or storage sit behind it.
_Avoid_: PCC, grid connection point, interconnection point

**MV interconnection / HV interconnection**:
The two ways a plant can meet the grid. An MV interconnection has no dedicated HV
transformer: the point of connection sits directly at MV, one level above the stations. An
HV interconnection inserts a transformer between the point of connection and the MV busbar,
stepping the export up to a higher voltage. Which one a design uses is a property of the
point of connection, not of any individual station.

**Busbar**:
The MV collection point that every circuit in a fleet hangs off. A busbar belongs to exactly
one fleet kind; a design with more than one fleet has one busbar per fleet.
_Avoid_: bus, collector bus

**Circuit**:
One radial daisy chain of stations run off a busbar by a single MV cable: the busbar feeds
the first station, that station feeds the next, and so on to the end of the chain. A fleet's
stations are grouped into as many circuits as the cable current limit demands.
_Avoid_: feeder, string (string is reserved for PV DC strings, a concept this tool does not model)

**Station**:
One MV/LV conversion point on the diagram: a transformer station, plus — depending on fleet
kind — the inverters or PCS units behind it. The generation or storage equipment behind a
station is accounted for through the fleet's aggregate power rather than as a thing of its
own, so a station's identity in this project is carried by the transformer station it names.
A station is the instance drawn on the canvas; the transformer station is the product it
names, and the two are never the same word.
_Avoid_: substation (substation refers to the shared HV/MV transformer block, a different
node on the diagram), MV/LV transformer, transformer station (that is the product, not the
node)

**Transformer station**:
A real MV/LV product a supplier sells, identified the way a quote identifies it, and the unit
a station catalogue entry describes. It is the whole enclosure — the transformer, its MV
switchgear, its control cabinet and its UPS — but only the transformer's own figures are read
by the sizing engine; the rest is recorded and shown. One catalogue entry per model number,
so two ratings of the same physical enclosure are two entries, not one entry with variants.
_Avoid_: MVS, medium-voltage substation (the supplier's word for it, and it collides with
substation), station transformer, MV/LV transformer, station (that is the node on the
diagram)

**AC power at ambient**:
The rated apparent power of a transformer station, which is only meaningful alongside the
ambient temperature it was measured at. Suppliers publish a single figure and usually leave
the temperature implicit; this project makes it explicit, holding a rating per ambient and
never interpolating between them. A design asking for an ambient the entry does not publish
is warned and falls back to the figure for the nearest published ambient at or above it — a
hotter rating is a lower one, so the station is understated rather than invented.
_Avoid_: rated power, nameplate rating (both drop the temperature, which is the whole point)

**Technology**:
The set of fleet kinds a design is permitted to contain — `pv`, `bess` or `hybrid` — declared
when the design is created and changed only by cloning the design into a new one. It is a
declaration rather than a description: it states what the design is for, and the interface is
built to match it, so the controls and palette items belonging to an excluded fleet kind are
never shown. A design's technology is authoritative over its diagram, but is enforced only by
what the palette offers, not by validation.
_Avoid_: project type (technology belongs to the design, not the project), design type,
fleet mix, asset class

**Fleet kind**:
The discriminator that says what a station is generating or storing: `pv` or `bess`. Every
station has exactly one fleet kind, and it determines which catalogues, labels and
compliance checks apply to that station.
_Avoid_: station type, asset class (asset class is fine in prose describing the domain, but
the model's own name for the concept is fleet kind)

**Fleet**:
The set of stations of one fleet kind behind one point of connection, sized and arranged as
its own independent cascade. A hybrid design has two fleets — one PV, one BESS — each with
its own busbar, its own circuits, and its own loading limit. Historically the word has meant
"every station in the design"; that usage is being retired in favour of "one fleet kind's
stations," and code or prose that still means the old, undifferentiated sense should say so
explicitly rather than relying on the bare word.
_Avoid_: plant (plant means the whole design, both fleets together)

**Loading**:
A station's or a fleet's power drawn as a fraction of its rated power. Every station within
a fleet runs at the same per-unit loading — the fleet's rating is shared out among its
stations in proportion to each one's own rating. A maximum loading limit is a compliance
threshold; a fleet that would need to run above it fails the loading check. PV and BESS
fleets can carry different maximum loading limits, reflecting their different duty cycles.
_Avoid_: utilization (utilization is used for a different, cable-current-based check),
load factor

**Auxiliary load**:
A fixed, worst-case power draw attached to a busbar that is not routed through any station —
the substation's own housekeeping load, or a BESS solution's supplier-specified auxiliary
consumption. It is a lumped figure, not a curve over time, and it enters the plant's power
balance only below the export step, never inflating the power a station or a PCS is sized for.

A supplier's figure can be **unpublished**, which is not the same as zero: the busbar total is
then understated by that solution's real draw, and the design says so in a warning rather than
inventing a number or refusing to solve.
_Avoid_: parasitic load, house load

**BESS solution**:
A named battery product, selected from a catalogue and identified the way a supplier quote
identifies it: brand, series and model number. It fixes the nominal energy of one container,
the rating and LV voltage of its PCS, the worst-case auxiliary draw, and the discharge
duration its model number declares. Choosing a BESS solution is choosing a real product, not
filling in a spec sheet by hand.
_Avoid_: BESS product, battery model

**Container**:
One physical enclosure of battery cells and its share of conversion equipment, as offered by
a BESS solution. The number of containers behind a station comes from the pairing between that
station's transformer and its solution — read, never computed, interpolated or rounded. It can
be overridden on a station that is only partially populated, which is the one place a
container count is a judgement rather than a supplier's figure.
_Avoid_: battery unit, pack

**Pairing**:
The record, carried by a BESS station transformer, of which BESS solutions it is actually sold
with and how many containers it serves for each. It exists because a container is not a
complete station: a transformerless product emits LV and reaches the MV busbar only through a
station transformer its own datasheet says nothing about. A solution and a station transformer
that are not paired cannot be combined, however well their voltages happen to agree.
_Avoid_: compatibility, match, association

**PCS**:
The battery-fleet name for the conversion equipment at a station — the point where DC storage
meets the AC collection network. It is the same position in the diagram that a PV fleet calls
the inverter: one physical role, two names, chosen by fleet kind so the result speaks the
language of the asset it describes.
_Avoid_: inverter, when the fleet kind is BESS

**Inverter**:
The PV-fleet name for the same conversion-level role that a BESS fleet calls the PCS. See PCS.
_Avoid_: PCS, when the fleet kind is PV

**Discharge duration**:
The number of hours a BESS fleet must sustain its point-of-connection power. A BESS solution
**declares** its duration through its model number rather than deriving it from energy and
power: the ST6900UX-4H sells 4 h, although its energy over its PCS rating works out to 3.84 h.
The nameplate is what gets procured, so the nameplate is what the catalogue records — the same
stance ADR-0002 takes for technology. As a project-level setting it is restricted to the
durations the drawn stations' own station transformers are paired to sell; a duration nobody
in the design is sold cannot be requested.
_Avoid_: duration, discharge hours (as a bare, unqualified term)

**Delivered energy**:
The total energy a BESS fleet can supply: each station's container count times the energy
of one container, summed across the fleet. A design meets its energy compliance check only
when delivered energy is at least the fleet's point-of-connection power times the discharge
duration.
_Avoid_: stored energy, capacity

**Simulated parameter / typed parameter**:
The two tiers every catalogue parameter falls into, and the distinction the catalogue is built
around. A **simulated** parameter is one the sizing engine reads — nominal energy, PCS rating
and LV voltage, discharge duration, auxiliary draw, AC power at ambient. A **typed** parameter
is structured, stored and shown, but never computed with: cell chemistry, dimensions, ingress
protection, the operating envelope, a ring main unit's protection functions. Both are
transcribed from a datasheet with equal care; only one of them can change a number in a design
review.

A typed parameter is defined by never being computed with, not by being numeric. A datasheet
row whose value is a set or an alternative rather than a number — the protection functions a
relay implements, the switchgear units on offer — is typed and transcribed verbatim, one row
to one field. What the tiers exclude is free-form prose, not non-numeric fact: there is no
third tier, and a datasheet row that will not survive verbatim transcription is not stored.
_Avoid_: display field, metadata (both blur the point, which is what the engine reads)

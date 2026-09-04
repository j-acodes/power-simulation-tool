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
One MV/LV conversion point on the diagram: a transformer, plus — depending on fleet kind —
the inverters or PCS units behind it. In the model today a station is represented purely as
its transformer; the generation or storage equipment behind it is accounted for only through
the fleet's aggregate power, not as a modelled object in its own right. A newcomer reading
the code should not expect to find a distinct "station" entity — what exists is a
transformer standing in for one.
_Avoid_: substation (substation refers to the shared HV/MV transformer block, a different
node on the diagram), MV/LV transformer

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
_Avoid_: parasitic load, house load

**BESS solution**:
A named battery product, selected from a catalogue, that fixes everything the sizing of a
BESS station depends on: the energy in one container, the power and LV voltage of one PCS,
the worst-case auxiliary draw, and the container count the supplier offers at each discharge
duration. Choosing a BESS solution is choosing a real product, not filling in a spec sheet by
hand.
_Avoid_: BESS product, battery model

**Container**:
One physical enclosure of battery cells and its share of conversion equipment, as offered by
a BESS solution. The number of containers behind a station comes straight from the solution's
own table for the chosen discharge duration — it is read, never computed, interpolated or
rounded.
_Avoid_: battery unit, pack

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
The number of hours a BESS fleet must sustain its point-of-connection power. It is a
project-level setting, restricted to whichever durations the chosen BESS solution actually
offers — a duration the solution does not sell cannot be requested.
_Avoid_: duration, discharge hours (as a bare, unqualified term)

**Delivered energy**:
The total energy a BESS fleet can supply: each station's container count times the energy
of one container, summed across the fleet. A design meets its energy compliance check only
when delivered energy is at least the fleet's point-of-connection power times the discharge
duration.
_Avoid_: stored energy, capacity

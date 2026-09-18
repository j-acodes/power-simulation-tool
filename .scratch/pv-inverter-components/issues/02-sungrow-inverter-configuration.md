# 02: Configure a Sungrow inverter inside a PV station

**What to build:** A sizing engineer can choose the Sungrow SG350HX-20 as a catalogue inverter
inside a paired Sungrow PV Transformer Station, choose an integer count up to that station's
physical maximum and retain the configuration in the diagram. The catalogue exposes the inverter
and pairings end to end, the inspector enforces selection order and count bounds, and hand-edited
payloads with unknown pairings or invalid counts are rejected. The inverter is never a canvas
node or standalone palette item.

**Blocked by:** 01: Make the specification view product-generic.

**Status:** done

- [x] SG350HX-20 is a first-class curated catalogue product with identity, simulated data, typed data and provenance
- [x] Each supported Sungrow PV Transformer Station exposes SG350HX-20 pairing, maximum count and default count
- [x] Maximum/default counts are 10, 14, 20, 22 and 28 for the five Sungrow station ratings
- [x] Station configuration stores one catalogue inverter model and one integer count
- [x] Inspector selection is station first, then allowed inverter, then bounded count
- [x] Unknown inverter, unpaired inverter, count below one and count above maximum are structured validation failures
- [x] The catalogue and placed station open separate station and inverter specifications
- [x] No inverter node kind, canvas node or standalone palette item exists
- [x] Catalogue, diagram validation, API-contract and focused frontend tests pass
- [x] Python and frontend typechecking pass

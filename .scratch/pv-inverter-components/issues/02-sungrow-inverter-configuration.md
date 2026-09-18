# 02: Configure a Sungrow inverter inside a PV station

**What to build:** A sizing engineer can choose the Sungrow SG350HX-20 as a catalogue inverter
inside a paired Sungrow PV Transformer Station, choose an integer count up to that station's
physical maximum and retain the configuration in the diagram. The catalogue exposes the inverter
and pairings end to end, the inspector enforces selection order and count bounds, and hand-edited
payloads with unknown pairings or invalid counts are rejected. The inverter is never a canvas
node or standalone palette item.

**Blocked by:** 01: Make the specification view product-generic.

**Status:** ready-for-agent

- [ ] SG350HX-20 is a first-class curated catalogue product with identity, simulated data, typed data and provenance
- [ ] Each supported Sungrow PV Transformer Station exposes SG350HX-20 pairing, maximum count and default count
- [ ] Maximum/default counts are 10, 14, 20, 22 and 28 for the five Sungrow station ratings
- [ ] Station configuration stores one catalogue inverter model and one integer count
- [ ] Setup/inspector selection is station first, then allowed inverter, then bounded count
- [ ] Unknown inverter, unpaired inverter, count below one and count above maximum are structured validation failures
- [ ] The catalogue and placed station open separate station and inverter specifications
- [ ] No inverter node kind, canvas node or standalone palette item exists
- [ ] Catalogue, diagram validation, API-contract and focused frontend tests pass
- [ ] Python and frontend typechecking pass

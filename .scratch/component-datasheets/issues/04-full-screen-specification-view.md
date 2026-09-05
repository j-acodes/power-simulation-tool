# 04: Read a component's full specification full-screen

**What to build:** A sizing engineer selects a catalogue component and opens its complete
published specification full-screen, reads it, and presses Escape to return to exactly where they
were.

This ticket lands both halves of the feature at once: the **typed** parameters themselves — every
published figure that is stored and displayed but never computed with — and the view that
displays them. Landing the fields alone would be verifiable only by reading an API response.

For a BESS solution the typed tier is: cell chemistry, DC voltage window, AC voltage window, AC
current per PCS, power factor at nominal power, reactive power range, nominal frequency, current
distortion, isolation method, dimensions, weight, ingress protection, corrosion class, operating
temperature range, operating humidity range, maximum operating altitude, cooling method, datasheet
URL, datasheet version, and a preliminary flag. For a BESS station transformer: model, vector
group, cooling, datasheet URL, and its pairings.

There is no free-form tier. Prose rows such as a fire-suppression component list or a compliance
standard list are not stored at all.

The view is a full-screen overlay over the current view, dismissed with Escape, leaving the canvas
mounted beneath — not a route, because it must be reachable from a canvas without losing diagram
state. It is **read-only**; editing stays in the Inspector.

It leads with a compact block of the parameters the engine consumes, then the typed specification
grouped as the datasheet itself groups it — DC side, AC side, physical, environmental — then the
pairings, then the datasheet link. **Leading with the simulated subset is the entire point of the
view:** the engineer must see in one glance what the tool knows versus what the datasheet says.

Only a URL is stored for the datasheet, never a PDF, and it may be empty — in which case no link
is shown rather than a dead one.

Reuse the existing modal shell, which already provides a full-screen size and Escape handling, and
the existing read-only detail-row and section-title idioms. Do not introduce a second overlay
mechanism.

**Blocked by:** 01 (Reshape the BESS solution around a declared discharge duration), 02 (Pair a
station transformer with the solutions it is sold with).

**Status:** ready-for-agent

- [ ] Every typed parameter listed above is stored, served by the catalogue endpoint and typed in
      the frontend, for both BESS solutions and BESS station transformers
- [ ] No free-form or untyped key/value tier exists anywhere in the model or the payload
- [ ] Selecting a catalogue component in the palette offers a way to open its specification
      full-screen
- [ ] The overlay renders the simulated parameters in their own block, before the rest of the
      specification
- [ ] The remaining parameters are grouped as the datasheet groups them, not alphabetically or
      as one flat list
- [ ] A station transformer's specification shows the solutions it is paired with, and a
      solution's shows the station transformers it is paired with
- [ ] A datasheet link is shown when a URL is present and nothing is shown when it is empty
- [ ] An entry whose datasheet is marked preliminary says so
- [ ] Escape closes the overlay and the underlying view is unchanged, including canvas state
- [ ] Nothing in the overlay is editable

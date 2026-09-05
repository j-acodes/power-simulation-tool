# 06: Expand a placed station into its specification

**What to build:** A sizing engineer clicks a station already on the canvas and opens its full
specification without losing the diagram — and clicking a BESS station transformer in the palette
finally shows something.

Three fixes to the same surface:

The Inspector gains an **expand** control for a catalogue-backed station, opening the
specification overlay from ticket 04. It is **hidden** for a custom station, whose parameters are
typed by hand and have no datasheet behind them — a specification sheet with a blank top half
teaches the engineer nothing except that they picked the wrong thing.

**BESS solutions become palette items**, alongside station transformers, so products live in one
place rather than half in a panel and half in a control buried behind a placed station.

The palette preview bug is fixed: selecting a BESS station transformer currently looks its key up
in the PV station transformer catalogue only, so the panel says "Loading…" indefinitely. It must
consult the BESS station transformer catalogue too.

**Blocked by:** 04 (Read a component's full specification full-screen).

**Status:** ready-for-agent

- [ ] Selecting a catalogue-backed station on the canvas offers an expand control that opens its
      specification full-screen
- [ ] The expand control is absent — not disabled — for a custom station
- [ ] Closing the overlay returns to the canvas with its state intact
- [ ] BESS solutions appear as palette items
- [ ] Selecting a BESS station transformer in the palette shows its preview instead of "Loading…"

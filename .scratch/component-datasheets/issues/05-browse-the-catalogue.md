# 05: Browse the catalogue without opening a project

**What to build:** A sizing engineer opens the catalogue, browses every component the tool knows
about, and opens any of them full-screen — without creating or opening a project first.

Today the catalogue has no home. A BESS solution appears in exactly one place: a control in the
Inspector, reachable only after a station is already on a canvas. There is no way to compare two
products, or look at one, without a design open.

The page is a new top-level route, independent of any project, listing all four catalogues: PV
station transformers, cables, BESS solutions, and BESS station transformers. BESS entries carry
the datasheet parameters from ticket 04; PV station transformers and cables show the parameters
they already have, and do **not** gain datasheet fields in this scope.

There is no technology filter. The page belongs to no design, so there is no technology to filter
by — the engineer sees everything.

Reuse the existing brand-grouping helper from the palette for the listing rather than writing a
second one.

**Blocked by:** 04 (Read a component's full specification full-screen).

**Status:** ready-for-agent

- [ ] A top-level route lists the catalogue and is reachable without opening a project
- [ ] All four catalogues appear on it
- [ ] BESS entries show their brand, series and model; PV station transformers and cables show
      the parameters they already carry
- [ ] Selecting any catalogue-backed row opens its specification full-screen
- [ ] The page offers no technology filter
- [ ] PV station transformers and cables have gained no datasheet fields

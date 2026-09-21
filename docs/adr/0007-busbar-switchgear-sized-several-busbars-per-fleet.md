# Busbar switchgear is sized, cable entry bounds circuit cables, and a fleet may have several busbars

Until now the busbar was a point with no equipment on it: circuits met there and nothing
limited them except the stations' own switchgear. Cable selection added parallel runs freely —
up to twelve — because nothing in the model said where those cables would land. And ADR-0001
allowed exactly one busbar per fleet, which caps a fleet at whatever one switchboard can carry
without the model ever saying so.

We now model the MV switchgear at both ends of every circuit:

- **Transformer stations** keep their catalogue switchgear rated current (ADR-0006), with the
  630 A fallback, checked against each station's through current.
- **Cable entry** — cables per phase and maximum cross-section — becomes a simulated catalogue
  parameter on each transformer station, falling back in the engine to two cables of 300 mm²
  with a notice. A circuit cable must fit the stricter cable entry of its two ends. Export
  cables are exempt.
- **Busbar switchgear** — the busbar, one feeder per circuit, and the MV export switchgear — is
  **sized** by the tool to the smallest standard rating that carries its design-point current:
  630, 800, 1250, 1600, 2000, 2500, 3150, 4000 A. No utilization margin, for the reason ADR-0006
  gives. An engineer may pin a rating; a pinned rating is checked instead.
- **A fleet may have several busbars in parallel.** Each has its own export switchgear and cable
  into the single shared HV transformer, or into the point of connection for an MV
  interconnection. Stage-1 planning opens another busbar when the next circuit would take a
  busbar past 4000 A or past 12 feeders; a drawn diagram keeps the busbars it was drawn with.

This supersedes ADR-0001's rule of exactly one busbar per fleet kind. Everything else in
ADR-0001 stands: one point of connection, one shared HV transformer, loading uniform per fleet,
the pro-rata reactive split and the multi-branch loss refinement.

## Why sized, not catalogued

A transformer station is a product: a supplier sells it with its switchgear fixed, and the
catalogue records what they publish. A busbar switchboard is designed per project — its panel
ratings are chosen to suit the plant — so there is no product to look up and no supplier figure
to fall back to. Sizing to a standard rating ladder is what the engineer would do by hand. The
owner considered entered figures with defaults and chose sizing for every part of the
switchboard, so that no part of one switchboard is treated differently from another.

## Why cable entry, and why only circuit cables

The terminals of a feeder or a station's switchgear accept a bounded number of cables per phase,
each up to a bounded cross-section. A model that adds parallel runs freely produces trunk
segments no one can terminate. Bounding circuit cables by the stricter of their two ends puts
that physical limit back. On today's catalogue it rarely binds against 630 A — two 300 mm²
cables give 664 A usable at the 0.80 utilization — but it binds as soon as a station publishes
a smaller entry. Export cables carry a whole busbar's current and routinely need more parallel
runs than any circuit entry allows; bounding them the same way would fail almost every design,
so they keep today's parallel-run behaviour.

The owner's earlier expectation of ~400 A per 30 kV circuit was reviewed and dropped as a
conservative habit: 630 A stands as the standard, so a 30 kV circuit may reach ~32.7 MVA.

## Considered options

- **One HV transformer per busbar.** More faithful to some large plants, but it rewrites the
  multi-branch loss refinement ADR-0001 names as the riskiest code. Deferred; needs its own
  record.
- **Busbar sections joined by a bus coupler.** Still one export, with the busbar rating split
  across sections. Rejected as more machinery than parallel busbars for the same effect on
  sizing.
- **Keeping one busbar per fleet** and flagging a fleet too big for it. Rejected by the owner:
  more detailed electrical design needs the plant to be drawable as built.

## Consequences

Failures follow ADR-0006's split. A station whose own current alone exceeds its own switchgear
rating, or its own cable entry, is a hard error. Anything collectively too heavy — a circuit
over a station's rating, a segment no admissible cable fits, a pinned rating too small — still
solves and is flagged where it happens.

The flat 400 A circuit cap is retired as ADR-0006 decided; its parked ticket and the ticket
showing the binding limit are absorbed into this work, so the golden baseline moves once.

Diagram JSON gains busbar switchgear pins and loses the one-busbar-per-kind rule; the saved
settings lose `max_circuit_current_a`. There are no migrations, so the database is reset when
this ships.

Out of scope: short-circuit and short-time withstand of the sized switchgear, HV-side
switchgear, one HV transformer per busbar, and installation derating of cable ampacity.

## Amendment: 300 mm² fallback

At implementation (2026-09-21) the owner lowered the cable-entry fallback from 2 × 630 mm² to
2 × 300 mm², and the same figure applies at the busbar end of a circuit. Two 300 mm² cables still
carry more than a 630 A station switchgear allows, so the station rating stays the usual binding
limit.

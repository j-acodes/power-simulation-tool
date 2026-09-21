# 04: Pinned switchgear ratings

**What to build:** the engineer can pin any busbar switchgear rating — the busbar, the export
switchgear, or an individual feeder — from the busbar inspector. Pins are optional per-busbar
values in diagram JSON. A pinned rating is checked, never resized; one smaller than its current
still solves and is flagged at the busbar, naming which part and by how much it is short. The
inspector and PDF mark each rating as sized or pinned.

**Blocked by:** 03.

**Status:** done

- [x] A pinned rating is reported exactly as pinned, never replaced by a sized value
- [x] A pinned rating below its current solves and raises an issue on the busbar node naming the part and the shortfall
- [x] Removing a pin returns that part to sizing
- [x] Diagram JSON without pins solves identically to ticket 03's behaviour
- [x] Inspector can set and clear each pin, and marks sized vs pinned (Vitest); PDF marks the same
- [x] Full README checks pass; report states whether the diagram JSON change needs a DB reset

## Comments

Shipped. Pins are busbar props: `busbar_switchgear_pin_a`, `export_switchgear_pin_a`,
`feeder_switchgear_pins_a` (keyed by the circuit's trunk edge id; a key for a missing edge is
ignored). The inspector offers "Sized" or a ladder rating. No DB reset needed: design payloads
are untyped dicts and an absent pin solves as sized (golden diff additive only).

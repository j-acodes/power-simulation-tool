# 04: Pinned switchgear ratings

**What to build:** the engineer can pin any busbar switchgear rating — the busbar, the export
switchgear, or an individual feeder — from the busbar inspector. Pins are optional per-busbar
values in diagram JSON. A pinned rating is checked, never resized; one smaller than its current
still solves and is flagged at the busbar, naming which part and by how much it is short. The
inspector and PDF mark each rating as sized or pinned.

**Blocked by:** 03.

**Status:** ready-for-agent

- [ ] A pinned rating is reported exactly as pinned, never replaced by a sized value
- [ ] A pinned rating below its current solves and raises an issue on the busbar node naming the part and the shortfall
- [ ] Removing a pin returns that part to sizing
- [ ] Diagram JSON without pins solves identically to ticket 03's behaviour
- [ ] Inspector can set and clear each pin, and marks sized vs pinned (Vitest); PDF marks the same
- [ ] Full README checks pass; report states whether the diagram JSON change needs a DB reset

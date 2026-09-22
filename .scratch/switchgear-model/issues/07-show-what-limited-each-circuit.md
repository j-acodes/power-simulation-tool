# 07: Show what limited each circuit

**What to build:** for every circuit, results and the PDF report name the limit that decided its
size — one of station switchgear, feeder, cable entry, or feeders per busbar — and show each
station's through current beside its switchgear rated current. Every fallback used (switchgear
rated current, cable entry) is visible as a notice. Absorbs the superseded ticket 04 of
`mv-switchgear-limits`.

**Blocked by:** 02, 04, 06.

**Status:** done

- [x] Each Stage-1 circuit reports exactly one binding limit; a test covers each of the four
- [x] A drawn circuit reports the limit it is closest to, not a planning decision it did not take
- [x] Results table shows through current vs switchgear rated current per station (Vitest)
- [x] PDF carries the binding limit per circuit and the per-station figures
- [x] Full README checks pass, plus a browser check of the results view against a disposable DB

## Comments

**2026-09-22, owner decisions before implementation.**

- *Feeders per busbar is not a circuit limit.* Ticket 06 opens another busbar instead of
  enlarging circuits, so the feeder count never decides a circuit's size. Each circuit reports one
  of three limits: station switchgear, cable entry, feeder. Each busbar shows its feeder count
  against the feeders-per-busbar setting and its current against 4000 A.
- *One rule for every circuit.* A Stage-1 plan becomes an ordinary drawn diagram, so the solve
  cannot tell a planned circuit from a drawn one. The binding limit is the one with the least
  headroom in amperes: station switchgear = min over stations of (rated − through current);
  cable entry = min over segments of (admissible-cable ceiling within the stricter cable entry of
  both ends − segment current); feeder = (pinned rating, else the 4000 A ladder top) − head
  current. Ties: station switchgear, then cable entry, then feeder. On a planned circuit this is
  the limit that decided its size, because every station in it is the same model.

**2026-09-22, shipped in `0d2e923`.** `circuit_binding_limit` in the engine feeds both the solve
payload (`feeder_binding_limit` per busbar; `through_current_a` and `switchgear_rated_current_a`
per station) and the PDF. The golden baseline was regenerated for the new keys only: the semantic
differ showed every change as an added key, with no value moved. The browser check ran against a
built frontend on :8765 with a disposable DB, because :8000 held the owner's backend. A seeded
150 MW / 30 kV plant showed every circuit bound by station switchgear (577 / 630 A), 6 / 12
feeders, 3,171 / 4000 A, and the cable-entry fallback notice. The PDF carries the same. PDF
notices were not added (out of scope).

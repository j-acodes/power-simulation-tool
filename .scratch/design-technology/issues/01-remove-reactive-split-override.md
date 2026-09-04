# 01: Remove the user-controlled reactive split

**What to build:** The reactive duty of the shared HV transformer is always divided between
the two fleets pro-rata by active power. A sizing engineer can no longer hand-tune one fleet
into carrying another's reactive duty, and the point of connection no longer offers a share
control.

This removes an escape hatch, not a behaviour. ADR-0001 already named pro-rata by active
power as the default; every design that never set an override must produce identical numbers
after this ticket. That equivalence is the whole verification.

Remove the share from the point-of-connection node's properties, from the graph validator
(including its dedicated validation issue for an out-of-range share), from the branch inputs
carried into the solver, and from the reactive split function, which now takes no share
argument. Remove the inspector control that fed it.

A design payload that still carries the property is ignored rather than rejected — an unknown
key in a diagram payload has always parsed permissively, and that stays true.

This ticket touches no technology code and shares no files with tickets 02 and 04. It edits
the inspector's point-of-connection block, which ticket 03 also edits; landing this first is
why it is numbered first.

ADR-0001 has already been amended to record this reversal — do not write a new record.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The reactive split function divides pro-rata by active power and takes no share argument
- [ ] The share is absent from the point-of-connection node properties, the branch inputs, and
      the graph validator; the out-of-range-share validation issue no longer exists
- [ ] The inspector's point-of-connection block no longer renders a share control
- [ ] A diagram payload still carrying the property parses without error and without effect
- [ ] A hybrid design that previously solved with no override set reproduces its results to
      within 1e-9
- [ ] Validator tests asserting the removed issue are updated in this ticket
- [ ] `pytest` passes
- [ ] Frontend typecheck, tests and lint pass

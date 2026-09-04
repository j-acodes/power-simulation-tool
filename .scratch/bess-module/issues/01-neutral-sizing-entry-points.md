# 01: Neutral sizing entry points and asset-neutral naming

**What to build:** Stage-1 sizing stops being named for PV, and gains a second entry point
that accepts an assigned reactive duty rather than deriving one from a power factor.

The existing entry point takes a chain, active power at the point of connection, and a power
factor target. Rename it to a generation-neutral name and keep the previous name exported as
a deprecated alias so nothing outside the project breaks without warning. Add a sibling that
takes active *and* reactive power at the head of the chain; the power-factor form computes
the reactive figure and delegates to it.

This is prefactoring. Ticket 05 splits a single point-of-connection reactive requirement
across two branches, at which point a branch's reactive duty is *assigned* to it and can no
longer be expressed as a power factor the branch owns.

Also neutralise the asset-specific naming in user-visible output: the API title, the PDF
report's default plant name, and the report footers.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The Stage-1 entry point has a generation-neutral name; the previous name remains
      importable from the package's public interface and emits a deprecation warning
- [ ] A reactive-in sibling entry point exists, taking active and reactive power at the head
      of the chain and returning the same result type
- [ ] The power-factor entry point computes reactive power from the target and delegates to
      the reactive-in form; both produce identical results for the same effective inputs
- [ ] API title, PDF default plant name and report footers contain no asset-class-specific
      wording
- [ ] Report and PDF assertions covering the old strings are updated in this ticket
- [ ] No numerical result changes anywhere; the full Python suite passes
- [ ] Frontend typecheck, tests and lint pass

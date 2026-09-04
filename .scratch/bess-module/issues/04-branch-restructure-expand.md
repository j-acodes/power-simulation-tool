# 04: Branch restructure (expand)

**What to build:** Nothing an engineer can see. This is the expand half of an
expand–contract: the engine learns to hold more than one fleet, while every existing caller
keeps working through unchanged accessors.

Today, uniform per-unit loading spans every drawn station: fleet apparent power is summed
across all of them and each station takes a share of one Stage-1 result, gated by one loading
flag. With two fleets that is wrong twice over — it would smear one asset class's inverter
power onto the other's stations, and one flag cannot express two different maximum loadings.

The replacement is **one plant layout per fleet**, each built from its own Stage-1 result and
its own maximum loading. Uniform per-unit loading survives *within* a fleet, unchanged, which
is what it always meant.

Architecture sizing splits into two halves: a per-branch half that produces a branch's
circuits and its busbar active and reactive totals, and a plant-level half that takes the
branch results and sizes the shared HV transformer and export cable once. The loss-refinement
fixed point generalises to per-branch correction scalars summed at the shared bus, with the
export step applied once.

The plant architecture object exposes its branches, and **keeps its previous single-fleet
accessors as compatibility properties** delegating to the sole branch when there is exactly
one. This is what keeps the reporting, PDF and result-mapping layers compiling untouched, and
it is removed in ticket 09.

**Acceptance is the entire existing test suite passing unedited.** No new tests, no adjusted
assertions. If an assertion needs changing to make this ticket pass, something is wrong with
the refactor — stop and say so rather than editing the assertion. Any numerical movement here
is a bug, not a design change.

**Blocked by:** 01 (Neutral sizing entry points)

**Status:** ready-for-agent

- [ ] One plant layout exists per fleet, each from its own Stage-1 result and its own maximum
      loading; per-unit loading remains uniform within a fleet
- [ ] Architecture sizing is split into a per-branch half and a plant-level half, with the
      shared HV transformer and export cable sized once at plant level
- [ ] The plant architecture exposes its branches, and its previous single-fleet accessors
      still work by delegating to the sole branch
- [ ] The loss refinement handles a list of branches, summing at the shared bus and applying
      the export step once
- [ ] **The complete existing Python suite passes with no test file modified in this ticket**
- [ ] Frontend typecheck, tests and lint pass

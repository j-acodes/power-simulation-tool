# 03: Update the glossary and the superseded sizing ticket

**What to build:** The project's documented vocabulary stops contradicting the code.

Three glossary entries hard-code the mechanism that tickets 01 and 02 removed:

- **BESS solution** and **Container** both define the container count as coming from "the
  solution's own table for the chosen discharge duration". That table no longer exists; the count
  comes from the pairing on the station transformer, and is overridable.
- **Discharge duration** is defined as "restricted to whichever durations the chosen BESS
  solution actually offers". It is now restricted to the durations available among the solutions
  paired with the chosen station transformer.

Two concepts are new to the domain and need entries of their own: the **pairing** between a
station transformer and the solutions it is sold with, and the distinction between a **simulated**
parameter — one the engine reads — and a **typed** parameter, which is structured, stored and
displayed but never computed with.

The BESS module's delivered sizing ticket states that container count is read from the duration
table and is never overridable. Both halves are now false. Amend it with a note recording what
superseded it rather than editing its history away — a shipped ticket claiming something untrue
is worse than one that says what changed.

Follow the glossary's own conventions, including the `_Avoid_` lines, and do not drift to
synonyms it explicitly rejects.

**Blocked by:** 02 (Pair a station transformer with the solutions it is sold with).

**Status:** ready-for-agent

- [ ] The BESS solution entry no longer references a per-solution duration table
- [ ] The Container entry describes the count as coming from the pairing, and as overridable
- [ ] The Discharge duration entry describes the restriction as coming from the station
      transformer's pairings
- [ ] A glossary entry exists for the pairing between a station transformer and its solutions
- [ ] A glossary entry exists for the simulated/typed parameter distinction
- [ ] The BESS module's sizing ticket carries a note naming what superseded its container-count
      and duration behaviour
- [ ] No glossary entry describes behaviour the code no longer has

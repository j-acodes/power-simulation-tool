# 02: A design declares its technology when it is created

**What to build:** Creating a design asks two questions instead of one — a name and a
technology, `pv` / `bess` / `hybrid` — and the answer is stored on the design, returned when
it is read, and available to the editor. The projects list shows each design's technology
alongside its name.

The creation dialog stays a single step: the existing prompt dialog gains a three-way picker
beside the name field. Both answers are required; cancelling behaves as it does today. This
is a dialog, not a wizard.

Technology is a non-nullable field on the design. There is no migration mechanism in this
project — the schema is created wholesale at startup — so the designs currently stored are
discarded and the database recreated empty rather than backfilled. **This is irreversible and
destroys every project and design in the database.** It is authorised because the contents
are test fixtures; confirm the database file is disposable before running it, and say so
rather than doing it silently.

Nothing reacts to technology yet — that is ticket 03. This ticket ends when an engineer can
create a PV, a BESS and a hybrid design, reopen each one, and see the technology persisted.

Technology is a declaration, authoritative over the diagram, and it is enforced only by what
the palette offers — see ADR-0002 before starting. Use the term "technology"; `CONTEXT.md`
records why "project type" is avoided.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The design record carries a non-nullable technology of `pv`, `bess` or `hybrid`
- [ ] The design-creation request requires a technology and rejects an absent or unrecognised
      value; design read responses expose it
- [ ] The "New design" dialog collects a name and a technology in one step, requires both, and
      cancels cleanly
- [ ] The projects list shows each design's technology
- [ ] The editor can read the open design's technology
- [ ] The database is recreated empty, and the engineer is told this is happening before it
      happens
- [ ] `pytest` passes
- [ ] Frontend typecheck, tests and lint pass

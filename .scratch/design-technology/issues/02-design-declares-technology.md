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

**Status:** done

- [x] The design record carries a non-nullable technology of `pv`, `bess` or `hybrid`
- [x] The design-creation request requires a technology and rejects an absent or unrecognised
      value; design read responses expose it
- [x] The "New design" dialog collects a name and a technology in one step, requires both, and
      cancels cleanly
- [x] The projects list shows each design's technology
- [x] The editor can read the open design's technology
- [x] The database is recreated empty, and the engineer is told this is happening before it
      happens
- [x] `pytest` passes
- [x] Frontend typecheck, tests and lint pass

## Comments

Implemented in 2ec3727.

**Backend.** `Design.technology` is a non-nullable `String` column (backend/models.py);
`Technology = Literal["pv", "bess", "hybrid"]` in schemas.py is the single source of the
allowed values, used by `DesignCreate`, `DesignSummary` and `DesignFull`. A missing or
unrecognised value 422s via Pydantic — no hand-written validator needed, which is the
"natural seam" the ticket pointed at. Covered by
`test_design_create_requires_valid_technology` in tests/test_persistence.py.

**Frontend.** Extended `PromptDialog`/`usePromptDialog` (components/Modal.tsx) with an
optional `technologyLabel` — when given, the dialog renders a required `<select>`
alongside the name input and the submit button stays disabled until both are filled;
omitted, it behaves exactly as before. This changed `prompt()`'s resolved type from
`string | null` to `{ value, technology? } | null`, so the other three call sites
(display name, new project, save-as-new-design) were updated to read `.value` — no
behaviour change for those. `Technology` type added next to `FleetKind` in types.ts.
`DesignMeta` in store.ts now carries `technology`, read off the design or off the 409
conflict's server copy, whichever `loadDesign` is loading.

**Save-as-new-design edge case (not in the ticket, but the same `createDesign` endpoint
that technology now gates):** the conflict dialog's "save as new design" action reuses
the conflicting design's own technology rather than opening a second picker — it's
saving a copy of the same diagram under a new name to escape a version conflict, not
choosing a technology, so no new UI was added for it.

**Database.** No `powertool.db` exists in this worktree, so nothing was deleted here.
The main checkout's `powertool.db` (`/Users/javieraguilar/projects/03-power-simulation-tool/powertool.db`,
outside this worktree) was left untouched — deleting it wasn't this ticket's call to
make unprompted. `scripts/reset_db.py` (documented in README.md) is the confirmed,
non-silent path: it prints the file's path and project/design counts, requires a typed
"yes", and only then deletes it. Run it before starting the app against that file.

Evidence: `pytest` 172 passed; frontend `npm run build` (tsc + vite) clean; `npm test`
59/59 (the "backend failed to start" line is `vite.config.ts`'s dev-only uvicorn
sidecar, unrelated — this worktree has no `.venv` of its own); `npm run lint` exits 0
(the five warnings shown are pre-existing, unrelated to this diff).

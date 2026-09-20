# 06: Cut over, reset and verify the complete feature

**What to build:** The application has one final PV inverter contract with no transitional legacy
path, the domain documentation describes the shipped behavior, the explicitly authorized local
database is empty, and the full verification matrix proves PV inverter behavior without regressing
BESS or accepted topology. Review findings are fixed before the branch is handed back.

**Blocked by:** 04: Generate and customize inverter-based PV stations; 05: Complete the Sungrow and Huawei PV catalogue.

**Status:** resolved

- [x] No production fallback synthesizes an inverter for a station that lacks one
- [x] The glossary and project status describe inverter composition, pairing, ambient power, loading and provenance
- [x] The exact active default SQLite target is re-resolved immediately before reset
- [x] The authorized database is permanently reset without backup and contains zero projects/designs
- [x] Test commands use a disposable database and never recreate data in the authorized database
- [x] Focused Python and frontend tests pass
- [x] The full Python suite passes
- [x] The full frontend suite passes
- [x] Frontend production build passes
- [x] Frontend lint passes with no new warnings
- [x] Documentation link and whitespace checks pass
- [x] Two-axis standards/spec code review is run against the branch base and all accepted findings are fixed
- [x] The specification and all ticket statuses record implementation evidence

## Implementation evidence

**Reset, 2026-09-20.** `DATABASE_URL` was unset, so the target re-resolved to
`sqlite:///powertool.db` → `/Users/javieraguilar/projects/03-power-simulation-tool/powertool.db`,
holding 4 projects and 8 designs. The owner authorized destroying all of them, including the
`HR023 - Novalja` project, after being shown the contents. `scripts/reset_db.py` deleted the
file; starting `backend.main:app` rebuilt it with the `projects` and `designs` tables and zero
rows, and `GET /api/projects` returned `[]`.

**Tests do not touch the authorized database.** `powertool.db` is byte-identical before and
after the full Python suite (md5 `66804de8f2a73677c9953c0633c740b7`), and still holds zero
projects and zero designs.

**Verification matrix.** 247 Python tests pass; 126 frontend tests pass across 12 files; the
production build succeeds with the pre-existing large-chunk warning only; lint reports the same
5 pre-existing React warnings and no new ones; `git diff --check` is clean.

**Behaviour changed after the first review** (commits `655eb83`, `de036c1`, `c077455`), so the
review checkbox above covers the branch base through `c077455`, not through `f9a28bf`:
a station is now deployed with its paired inverter at the pairing's maximum count rather than
arriving unconfigured; `default_count` is deleted from the catalogue, engine, API, types and
spec view, leaving `maximum_count` alone; the inverter select renders only where a station
declares more than one pairing; and the inspector can apply one catalogue model to every other
catalogue PV station, refilling each one's inverter and count behind a confirmation.

**Second review pass, covering `f9a28bf..HEAD`.** Standards found one duplication worth fixing:
the seed wizard re-implemented the "first pairing, filled to maximum" rule inline while
`inverterDefaults.ts` claimed to be the shared home of it, so a future change to the rule would
have had to land in two places. The wizard now calls `defaultInverterSelection`. Spec found no
code defect, but caught this specification itself still describing a pairing's `default_count`
after the field was deleted; the Solution and Implementation Decisions sections are corrected.

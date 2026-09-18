# 06: Cut over, reset and verify the complete feature

**What to build:** The application has one final PV inverter contract with no transitional legacy
path, the domain documentation describes the shipped behavior, the explicitly authorized local
database is empty, and the full verification matrix proves PV inverter behavior without regressing
BESS or accepted topology. Review findings are fixed before the branch is handed back.

**Blocked by:** 04: Generate and customize inverter-based PV stations; 05: Complete the Sungrow and Huawei PV catalogue.

**Status:** ready-for-agent

- [ ] No production fallback synthesizes an inverter for a station that lacks one
- [ ] The glossary and project status describe inverter composition, pairing, ambient power, loading and provenance
- [ ] The exact active default SQLite target is re-resolved immediately before reset
- [ ] The authorized database is permanently reset without backup and contains zero projects/designs
- [ ] Test commands use a disposable database and never recreate data in the authorized database
- [ ] Focused Python and frontend tests pass
- [ ] The full Python suite passes
- [ ] The full frontend suite passes
- [ ] Frontend production build passes
- [ ] Frontend lint passes with no new warnings
- [ ] Documentation link and whitespace checks pass
- [ ] Two-axis standards/spec code review is run against the branch base and all accepted findings are fixed
- [ ] The specification and all ticket statuses record implementation evidence

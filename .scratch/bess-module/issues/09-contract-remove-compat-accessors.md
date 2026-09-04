# 09: Contract — remove single-fleet compatibility accessors

**What to build:** Nothing an engineer can see. This closes the expand–contract opened in
ticket 04.

Ticket 04 kept the plant architecture's previous single-fleet accessors as compatibility
properties delegating to the sole branch, so that the reporting, PDF and result-mapping
layers could migrate incrementally instead of all at once. By the time tickets 05 to 08 are
done, every caller reads branches directly and those accessors have no remaining users.

Delete them. Two ways to read the same value is debt, and the reason for carrying it has
expired.

**Blocked by:** 05, 06, 07, 08

**Status:** ready-for-agent

- [ ] The single-fleet compatibility accessors added in ticket 04 are removed
- [ ] No caller anywhere reads a fleet's data other than through the branch structure
- [ ] No behaviour or numerical change
- [ ] Python suite, frontend typecheck, tests and lint all pass

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

**Status:** done

- [x] The single-fleet compatibility accessors added in ticket 04 are removed
- [x] No caller anywhere reads a fleet's data other than through the branch structure
- [x] No behaviour or numerical change
- [x] Python suite, frontend typecheck, tests and lint all pass

## Comments

Done in 3946a15. Scope came out wider than the ticket assumed in one direction and
narrower in another, both worth recording.

**Wider.** Tickets 05-08 migrated the API/PDF path but left the Streamlit-era path
untouched, so `powertool/report.py`, `powertool/diagram.py` and `app/streamlit_app.py`
were all still on the shims. They read `branches[0]` / `branch_refinements[0]` now.
`GraphInputs` had grown its own identical first-branch block after ticket 04; its only
remaining readers were tests, so it went in the same pass under criterion 2.

**Narrower.** `report.py` and `diagram.py` each take ONE Stage-1 result and so cannot
describe a hybrid at all. Rather than rewrite them (unrequested, and ticket 08 already
made the PDF the hybrid-capable artefact) they refuse a multi-branch plant and name the
fleets found — the stance fe004b4 took for the PDF. That refusal is new behaviour, which
the ticket's "no behaviour change" line does not cover, so it carries a test each.

`size_architecture` stays: it is the single-branch entry shim, not a compat accessor, and
it still has real callers.

`n_circuits`, `total_cable_loss_kw`, `total_transformer_loss_kw` and `all_current_ok` now
sum every branch instead of delegating to the sole branch. Identical for one branch, and
it let `map_results`' hybrid path drop its hand-rolled copies of the same sums.

Evidence: 8-design golden snapshot byte-identical (verified independently of the
implementing agent); 180 Python tests, frontend build, oxlint and 59 vitest tests green;
no test expectation changed, only accessor paths.

# D-ui (#76) — the interactive expert slice

Item `D-ui` of plan `rdr-interface-and-decorator`, resolved by
`/plan-item-resolve` in session_01WnFnM5sADR7Nmz5tMDHy1H.

## What was stalling it

A 50-thread review round opened on #76 between 2026-08-30T14:34Z and 17:13Z,
twenty-five minutes after the previous session posted its completion note and
stopped. None of it was recorded on the item, so the manifest read healthy.
Sixth instance of that staleness class on this plan.

## Plan, as carried out

1. Record the round as a blocker on the item before touching code. Done.
2. Apply the round: magics as classes with their own name enum and namespace-key
   enum; `%knows` → `%sufficient_conditions_for`; prompt sections as one class
   per situation; field docstrings under each field; abbreviations spelled out;
   inline imports hoisted; `rdr/__init__.py` restored to the base. Done in
   `a07a4458`.
3. Split the 1,456-line prompt-sections test into four files named for their
   subjects. Done in `a07a4458`.
4. Cover magic selection and registration, which were reachable only through a
   real terminal. Done — eight tests in `test_magic_registration.py`.
5. Hoist the file's remaining inline imports. Done in `c40da8fa`.
6. Reply to every thread; resolve the ones done as asked. Done — 45 resolved,
   5 replied to and left open.
7. Refresh the pull request description, the manifest and the roadmap, and
   republish the dashboard. Done.

## Verified

- `test_eql_rdr`: 532 passed, 2 skipped (524 baseline + 8 new).
- Rest of `test/krrood_test/`: byte-identical outcome to the baseline tree
  (2096 passed / 47 failed / 106 collection errors, all from optional
  dependencies missing in this container).
- `doc/eql/user/eql_rdr_conclusion_asking.md` executed as a notebook: passed.

## Outstanding

- **CI has never run on this branch** — zero check runs on every head it has
  had, so all the figures above are local measurements.
- **Five review threads deliberately left open**, each answered in its thread:
  the `match`/`case` suggestion (answered with a lookup table instead), the
  generated-model header (comes from a template on the base), the side-by-side
  labels (`case_table.py`, #79, already out of draft), `except Exception: pass`
  (nothing is raised there), and the `elision` rename (`rule_tree_view.py`,
  #67).
- **A defect in `.claude/hooks/plan_item_bootstrap.py`**: its `update`
  subcommand emits invalid YAML for any item whose `depends_on` list precedes
  the field being written — it re-emits the field indented under the last list
  entry. Reproduced on `D-ui` and `D-store`. The manifest here was hand-edited
  and saved with `save-plan.sh --manifest` instead. Belongs to whichever plan
  owns the plan tooling.

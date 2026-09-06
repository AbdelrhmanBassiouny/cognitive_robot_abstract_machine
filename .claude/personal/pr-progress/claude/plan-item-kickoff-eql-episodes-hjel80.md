# episodes-queried-by-eql — PR #278 (draft)

Plan `icra-foundation`, track `long-term-memory`. Base: #271
(`claude/icra-experiments-ormatic-episodes-ib9lr3`), which is open and not a
draft. Stack: #278 -> #271 -> #262 -> main.

## The plan

Long-term memory: the same EQL query language that asks a live world a question
asks the recorded episodes one, and gets domain objects back. With that, the
`Report` of an experiment is computed from the database rather than from the
results still in the process that made them.

1. `test/experiments_test/test_long_term_memory.py` — tests first (TDD).
2. `experiments/src/experiments/episodes/long_term_memory.py` — `LongTermMemory`
   over `ResultsDatabase`: `answer(query)`, `recall_trials(episode_identifier)`,
   `report_on(episode_identifier, metrics)`.
3. `experiments/src/experiments/scenarios/report.py` — `MeasuredTrial` protocol
   (`outcome`, `duration`), so a metric measures a live `Trial` and a
   `RecordedTrial` alike.
4. `experiments/scripts/generate_orm.py` — ignore `long_term_memory`, for the
   reason `recording` is already ignored: it holds a database, not a record.

Design decisions and their reasoning are in the plan's `roadmap.md` section
`episodes-queried-by-eql (#278), as planned 2026-09-06`.

## Done

- Setup check run; dashboard dependencies installed. `branch_base` was resolved
  by cutting this branch off #271 rather than off `integration`.
- Branch cut and pushed; draft PR #278 opened.
- Manifest recorded (branch/PR/session/`in_progress`) and roadmap section
  appended, both on `claude/personal-notes`.

## Next

- Write the tests, then the module, then the protocol, then the ignore list.
- Update the PR description if what it does changes.

## Known hazards

- **Nothing here runs in this container.** `test/experiments_test/conftest.py`
  imports `rclpy` and regenerates the ORM interface; `random_events` needs a C++
  library that will not build here. Everything is CI-verified, as #262 and #271
  were. So: no speculative EQL shapes. Only what
  `test/krrood_test/test_ormatic/test_eql.py` already proves — single-table
  column filters and many-to-one joins.
- **`plan_item_bootstrap.py` corrupts this manifest.** It renders item fields at
  4-space indentation (`ITEM_FIELD_INDENT`), but 22 of the 28 plans — this one
  included — put item fields at 2 spaces under a column-0 `- id:`. Its `open`
  subcommand therefore wrote invalid YAML and `save-plan.sh` rejected it. Worked
  around by editing `plan.yaml` by hand this run; the script itself is still
  broken and is not this PR's to fix.

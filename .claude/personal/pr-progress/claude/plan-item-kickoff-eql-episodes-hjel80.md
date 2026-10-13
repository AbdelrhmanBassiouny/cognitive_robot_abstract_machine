## Next
- CI is the only verification available; read it when it reports and fix what
  it finds.
- Keep the PR description matching the work if it changes.


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

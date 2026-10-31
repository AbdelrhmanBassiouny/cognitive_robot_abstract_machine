# D-core-underspecified (#64) — progress

## State (2026-10-31)
- `67250a7d5` adopted main's renamed Match properties (`_type_`/`_variable_`/`_matches_with_variables_`), the cause of the red `test_each_lib (krrood)` and of the `integration-conflict` label.
- `a89175571` answers the 2026-10-31 review thread: `is_ellipsis_target`, `is_unbounded_iterable` and the `unbounded_iterable_origins` classproperty now live on `RDRMatchParser`. Thread replied to and resolved. `test_eql_rdr` 54 passed.
- Carried into #65 (`03bb9e461`, 63 passed). No other stacked branch touches this module.
- The PR stays ready (promoted as cram2 #658).

## Next
- Confirm the fork CI is green on `a89175571` (the user reran a failed job on `67250a7d5`), then drop `integration-conflict`.
- #66, #67, #98, #159, #210 still need restacking onto main (`AGENTS.md` conflict, plus `core/base_expressions.py` on all but #66).

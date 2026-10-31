# D-core-underspecified (#64) — progress

## State (2026-10-31)
- Fixed the red `test_each_lib (krrood)`: `main` now carries #192 (cram2 #662), which renamed `Match.type` / `.variable` / `.matches_with_variables` to `_type_` / `_variable_` / `_matches_with_variables_`. `67250a7d5` adopts those names at the eight sites the 2026-09-19 triage comment listed (5 in `rdr/underspecified.py`, 3 in `test_underspecified_match.py`). The test edits change only which property name is read. No assertion changed.
- Verified locally: `test/krrood_test/test_eql_rdr` 54 passed (was 9 failed in `test_underspecified_match.py`).
- The formatter hook's churn (one-line docstrings reflowed to multi-line in untouched code) was reverted per the plan's standing rule. `black --check` is clean.
- The pull request stays ready for review: it is promoted (cram2 #658 is open, with no reviews; its only red check is giskardpy's unrelated `test_integration_daisy`).

## Next
- Confirm the fork CI is green on `67250a7d5`, then the `integration-conflict` label can come off (its cause was this rename).
- Carried into #65 `D-core-corner-case` (`e8b9ffe9f`, clean merge, 63 passed). Not carried into #66, #67, #98, #159 or #210: they never took `main`'s last merge, and merging hits `AGENTS.md` (plus `core/base_expressions.py` on all but #66). That restack belongs to each branch.

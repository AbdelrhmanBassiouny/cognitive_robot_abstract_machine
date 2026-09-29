PR #469 (draft, label bug): keep an EQL evaluation's context current while its results are closed.
Stacked on upstream cram2#579 (Jonas, commit 463f655); fork base branch `transformation_rules` mirrors #579 head 0ee271de27.

Done:
- Added EvaluationContext.as_current(); iterate_as_current closes results under it (commit 494693038c).
- Tests: close-path (TDD, failed first), interleaved same-query, unrelated-while-suspended.
- krrood test_eql: 1315 passed, 3 skipped locally (py3.12, test_typing excluded: no mypy).

Next:
- Wait for CI / user review. When #579 moves, re-sync `transformation_rules` from refs/pull/579/head and merge into this branch.
- Out of scope, possible follow-up: use as_current() in rdr/observer.py, experiments monitoring_profile.py / confidence_guard.py.

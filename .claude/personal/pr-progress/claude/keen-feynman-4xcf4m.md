## Plan
- Core is declared once in `[tool.krrood.core-boundary]` of krrood/pyproject.toml. `CoreBoundaryChecker` (rule `CORE_LOADS_ONLY_CORE`, run by `krrood check` and the pre-commit hook) checks the module-level import graph; a one-interpreter runtime backstop test catches what the graph cannot see. No import-linter, no offender lists. Moving to per-distribution maps belongs to `krrood-distributions`, not here.

## Done
- Checker, rule, hook, docs, mimic-based checker tests, and the backstop fix that judges only packages a krrood module loads itself (695dbb7cb). CI at 695dbb7cb: all 18 checks green.
- Resolve of the conflict with main be69c37d5 in `test/krrood_test/test_development_tools/dataset_files.py` (both sides appended classes): merged in 57efc63de, keeping both. main's leading-preposition check flagged `with_requirements`, renamed `requirement_closure` in 21b9824c2.
- At 21b9824c2: merge probe CLEAN against be69c37d5; test_core_boundary + test_development_tools 64 passed (Python 3.12 venv, `--confcutdir=test/krrood_test`); pre-commit and `krrood check --all-lines` on the branch's source files clean. Upstream: no upstream pull request for this branch.
- Carried into #547: restack pushed claude/bold-ramanujan-vb0e9c at 36dd083ab.

## Next
- Read CI at 21b9824c2 and at #547's 36dd083ab (not checked yet).

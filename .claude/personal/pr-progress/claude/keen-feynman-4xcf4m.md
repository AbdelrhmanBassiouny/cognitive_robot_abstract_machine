## Plan
- Core is declared once in `[tool.krrood.core-boundary]` of krrood/pyproject.toml. `CoreBoundaryChecker` (rule `CORE_LOADS_ONLY_CORE`, run by `krrood check` and the pre-commit hook) checks the module-level import graph; a one-interpreter runtime backstop test catches what the graph cannot see. No import-linter, no offender lists.

## Done
- Checker, rule, hook, docs and mimic-based checker tests (PR #546 head 73f811137).
- Resolve of the failing krrood CI job (read at 73f811137): the backstop flagged cffi, charset-normalizer, cython, pymongo and pytz, which libraries load on their own account when installed in the full workspace env (scipy -> cython, numpy.f2py -> charset-normalizer, dnutils -> pymongo, pandas -> pytz). Fixed in 695dbb7cb: the backstop reads each loaded package's importer from `-X importtime` and judges only packages a krrood module loads itself. Reproduced locally for cython, pymongo and pytz; cffi was not reproduced. Mutation check: a dynamic `importlib.import_module("mypy")` in a core module still fails it.
- Local: test_core_boundary and test_core_boundary_checker, 11 passed; ruff/docformatter, `krrood check` on the changed files clean.

## Next
- Re-read CI on 695dbb7cb. Not checked yet: the krrood job after the fix.
- Failed for a reason unrelated to the code at 73f811137: robokudo and physics_simulators (runner out of disk while installing `ortools`/`polars-runtime-32`). `cognitive_robot_abstract_machine` also failed; only its post-job log was read, so its cause is not confirmed. Re-run those jobs if they fail the same way.
- Merge conflict with main: none at 73f811137 (merge probe, base d938a05b9). Upstream: no upstream pull request for this branch.
- Fix carried into #547: `restack` pushed claude/bold-ramanujan-vb0e9c at 4ba367282 (its CI not read). The full stack pass did not run: attaching the upstream was denied, so the stack is not fully checked.

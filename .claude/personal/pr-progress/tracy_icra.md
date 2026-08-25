## PR #569 - single source of truth for dependencies (branch claude/single-source-dependencies, worktree /home/bass/Projects_2/cram-single-source-dependencies)

Plan: every workspace member declares `[project] dependencies` statically (incl. imported
sibling packages), requirements*.txt deleted, dev lists -> `dev` extras, consumers switched
to `pip install -e .`, guard test in test/version_test/test_dependency_declarations.py.

Done (2026-08-25): all of the above implemented, committed (4b4cfdf4d), pushed, draft PR
#569 opened against cram2/main. Verified: uv lock resolves, random_events sdist metadata
correct, `pytest test/version_test` 21 passed (guard test fails 18/20 on old main).

Next: wait for CI on #569 and review. Open decisions flagged in the PR: giskardpy /
physics_simulators / robokudo are not on PyPI (declared deps make PyPI installs of
coraplex / semantic_digital_twin fail at resolve time); dependency lists were migrated
faithfully, cleanup (dev tools in krrood runtime deps, `pathlib`, `pip`) is a follow-up.

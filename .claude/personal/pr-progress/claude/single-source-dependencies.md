## PR #197 (fork) / #569 (upstream cram2) - single source of truth for dependencies

Branch: claude/single-source-dependencies.

Plan: every workspace member declares `[project] dependencies` statically (incl. imported
sibling packages), requirements*.txt deleted, dev lists -> `dev` extras, consumers switched
to `pip install -e .`, guard test in test/version_test/test_dependency_declarations.py.

Done (2026-08-25): all of the above implemented, committed (4b4cfdf4d), pushed, draft PR
#569 opened against cram2/main. Verified: uv lock resolves, random_events sdist metadata
correct, `pytest test/version_test` 21 passed (guard test fails 18/20 on old main).

Done (2026-08-26): reviewer read `imported <= declared` as a size comparison. It was
already subset, but rewritten as `imported - declared == set()` (a1498c80) so the reading
is unambiguous and the failure names the missing package. Verified by deleting
semantic_digital_twin from coraplex's deps: fails with `{'semantic-digital-twin'} == set()`;
otherwise 20 passed. Draft fork PR #197 opened against AbdelrhmanBassiouny/main as asked.

Next: nothing queued for this session. Note the push also moved upstream #569's head (the
branch is shared); #569 was left untouched otherwise. Open decisions still flagged on #569:
giskardpy / physics_simulators / robokudo are not on PyPI (declared deps make PyPI installs
of coraplex / semantic_digital_twin fail at resolve time); dependency lists were migrated
faithfully, cleanup (dev tools in krrood runtime deps, `pathlib`, `pip`) is a follow-up.

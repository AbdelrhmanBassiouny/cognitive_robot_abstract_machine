## eql-verbalization / p4-sdt-migration — resolve session (2026-07-30)

Session role: `/plan-item-resolve eql-verbalization p4-sdt-migration`. No code
written yet — research + plan only.

### What the item is

P4 = PR #33 (`eql-symbolic-function-sdt`, base `main`, open + draft, label
`needs-resolution`). Migrate sdt's `reasoning/{predicates,queries,robot_predicates}.py`
off `@symbolic_function` onto `Predicate`/`SymbolicFunction`, apply every wording
decision from the #33 review, and regenerate the sdt verbalization snapshot.

### State found

- Dependencies P1 (#86), P2 (#87), P3 (#88) all merged; readiness script reports
  `is_ready: true` for all three.
- Branch is 605 commits behind `main` (merge-base `2c1ee15b`). `git merge-tree`
  gives 5 conflicts: `krrood/.../core/base_expressions.py`,
  `sdt/.../reasoning/queries.py`, `sdt/.../semantic_annotations/semantic_annotations.py`,
  and modify/delete on `test/krrood_test/.../test_verbalization_surfaces.py` +
  `verbalization_surfaces.py` (both deleted on `main`).
- Silent (non-conflict) staleness: the framework the branch carries
  (`verbalization/surface_verification.py`, `VerbalizationSurface`,
  `SymbolicSurfaceSnapshot`, `SURFACES`) is superseded on `main` by
  `entity_query_language/testing/result_verification.py`
  (`VerbalizationResult`, `VerbalizationResultsOfPackage`, `results`) plus a
  generator (`testing/result_generation.py`) that krrood's conftest runs each test
  run — the sdt snapshot must be generated, not hand-written.
- 36 of 37 review threads unresolved.
- CI green on head `dc6948ec`, but that run predates 605 commits of `main`.

### Next

Present the resolve plan via ExitPlanMode; settle the branch question
(continue on `eql-symbolic-function-sdt`/#33 vs the session's designated
`claude/eql-verbalization-p4-sdt-nbmu16`) before any push.

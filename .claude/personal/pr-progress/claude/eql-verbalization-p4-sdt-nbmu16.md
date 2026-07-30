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

### Decisions settled with the user (2026-07-30)

- **Branch**: continue on `eql-symbolic-function-sdt` / PR #33, *not* this
  session's designated `claude/eql-verbalization-p4-sdt-nbmu16` — the 36
  unresolved review threads have to be replied to and resolved in place.
- **Roadmap corrections**: edited `roadmap.md` directly (done — decision 9's
  `OPERAND_OVERRIDES` line superseded by `_example_operand_values_`; new "How the
  snapshot works now" section replacing the hand-written-tuple assumption), then
  `save-plan.sh` + dashboard refresh.
- **`Reachable` wording**: decision 11 — *"a Pose is reachable for the kinematic chain
  rooted at <root> and ending at <tip>"*. Root/tip stay named (decision 10's concision
  rule does not apply here).
- **First-mention type annotation** (*"a gripper of type HasTwoFingers"*): out of P4's
  scope, split into new item `p5-first-mention-type-annotation` (decision 12, added to
  `plan.yaml`, announced on #104 per the structural-change convention).

### Plan (approved, not yet implemented)

1. Merge `main` into the branch: `main` wins everywhere except sdt reasoning +
   `ormatic.py`'s `SymbolicCallable` exclusion. Delete `surface_verification.py`
   and the two krrood test surface files.
2. Rebuild the sdt snapshot on `VerbalizationResultsOfPackage` + wire
   `regenerate_verbalization_results` into `test/semantic_digital_twin_test/conftest.py`.
3. Apply the roadmap's P4 wording checklist, no-abbreviation sweep, `Noun` over raw
   `WordFragment`, and the `Pose`-hint investigation.
4. `regenerate_all_orm.py`, `format_docstrings.py`, run sdt + krrood suites.
5. Reply-and-resolve all 36 threads; refresh #33's description; update `plan.yaml`
   status/blockers.

Full plan file: `/root/.claude/plans/compiled-squishing-bachman.md`.

### Next

Start step 1 (the `main` merge) on `eql-symbolic-function-sdt`.

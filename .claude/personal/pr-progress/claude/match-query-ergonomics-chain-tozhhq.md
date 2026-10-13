## Next / outstanding
- Landing order with #196: adjacent lines of `_expression_signature`; second lander
  resolves one hunk. Recorded on both pull requests.
- The user-visible ranking repro over two aggregates of one kind needs #196 *and* this
  one; neither alone closes it.
- CI red on `test_each_lib (krrood)`, and it is not this diff:
  `test_draw_evaluated_tree_for_drawer_cabinet_rdr` loads an RDR model that
  `test_save_and_load_drawer_cabinet_rdr` writes, `test_results/` is gitignored, and CI
  runs `pytest -n auto`, so the loader can start before the saver has written anything.
  Measured both ways - the test alone with the generated directory removed fails
  identically with the diff reverted to `main` 2318e206, and the module under `-n 4` from
  a clean state fails 5/5 on the branch and 3/3 reverted. Diagnosis and a proposed fixture
  fix commented on #248; failed jobs re-run once. Not bundled in, being a second root
  cause in the RDR test suite. Fixed on its own branch at the developer's instruction:
  PR #251, `claude/rdr-world-saved-model-fixture`, draft with the `bug` label.


## Plan
1. Discharge the recorded blocker: #182 merged 2026-08-24, dependency `is_ready: true`. [done]
2. Re-measure the collision on today's `main`. [done - the paths differ and still compare
   equal, because the bogus reads build a truthy `Comparator`]
3. Failing tests first at the level the fix changes. [done - 4 assembler-level tests fail
   on `main`; the core `_structural_key_` tests cannot fail first, since the missing name
   is itself a symbolic attribute]
4. `_structural_key_` abstract on `MappedVariable`, stated by each of the five kinds;
   assembler reads it per step. [done]
5. Record manifest + roadmap section 25, open the draft PR, republish the dashboard. [done]

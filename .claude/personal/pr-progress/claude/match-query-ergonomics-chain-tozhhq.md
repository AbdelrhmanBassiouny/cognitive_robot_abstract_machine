# chain-signature-reads-attribute-only-names (PR #248, draft, `bug`)

Plan `match-query-ergonomics`, item `chain-signature-reads-attribute-only-names`,
branch `claude/match-query-ergonomics-chain-tozhhq` off `main` at 2318e206.

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

## Verification
- `test/krrood_test/test_eql`: 1276 passed, 3 skipped.
- Full `test/krrood_test`: 2258 passed, 5 skipped; the two `test_object_diagram`
  failures are this container's missing Graphviz `dot` binary (`/usr/bin/dot: not
  found`), the same pair every earlier session on this plan recorded.
- The recorded repro script prints `equal : False` on this branch and `equal : True`
  on `main`.

## Records written
- `plan.yaml`: status `in_progress`, blockers cleared, branch/PR/session recorded.
- `roadmap.md` §25; dashboard republished; tracking issue #181 and #196 commented.

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
  cause in the RDR test suite - worth its own item if the developer wants it tracked.

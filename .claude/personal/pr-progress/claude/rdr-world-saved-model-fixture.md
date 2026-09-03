# rdr-world saved-model fixture (PR #251, draft, `bug`)

Branch `claude/rdr-world-saved-model-fixture` off `main` at 69b2395a2. Not a
`match-query-ergonomics` item: it is the second root cause found while diagnosing that
plan's CI red on #248, in the RDR test suite rather than in EQL, and it is one pull
request rather than a tracked programme.

## The bug
`test_draw_evaluated_tree_for_drawer_cabinet_rdr` loads the model
`test_save_and_load_drawer_cabinet_rdr` writes; `test_results/` is gitignored, so in a
fresh checkout it exists only once the writer has run, and CI's `pytest -n auto` puts the
two on different workers.

## Plan
1. Reproduce on `main` from a clean state. [done - `RDRLoadError`, and identically with
   #248's diff reverted]
2. A `saved_drawer_cabinet_rdr` fixture writing into a directory named after the
   requesting test, reporting where and under what name. [done]
3. Both tests read it; the reader stops naming `"world_rdr"` itself. [done]
4. Draft PR with the `bug` label. [done - #251]

## Verification
- the reader alone from a clean state: passes; fails on `main`.
- the module under `-n 4` from a clean state: `6 passed, 1 skipped`, 5/5 runs (1 failed
  5/5 before).
- `test/krrood_test/test_ripple_down_rules` under `-n 4`: 76 passed, 2 skipped; the two
  `test_object_diagram` failures are this container's missing Graphviz `dot`.

## Next / outstanding
- Nothing outstanding beyond CI on the pull request itself.
- The old shared path `test_results/world_drawer_cabinet_rdr` now has no writer; it is
  gitignored output, so nothing references it.

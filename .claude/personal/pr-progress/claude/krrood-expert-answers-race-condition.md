## Plan (PR #73, branch claude/krrood-expert-answers-race-condition)

Task: fix flaky/parallel-unsafe `test_rdr_alchemy.py::TestAlchemyRDR::test_fit_*`
(FileNotFoundError under `pytest -n auto` on shared committed
`test_expert_answers/*.py` fixtures, root cause: `get_fit_scrdr`/`get_fit_mcrdr`/
`get_fit_grdr` in `test_helpers/helpers.py` construct `Human(answers_save_path=<shared
committed path>)`, and `Expert.__init__` always `os.remove()`s that file right after
loading when `append=False` - races any other worker reading/rewriting it).

Discovered mid-investigation: a SEPARATE, more fundamental bug was blocking any local
verification - `experts.py` writes/reads the answer delimiter single-quoted, but all 8
committed `.py` fixtures use double quotes, so zero answers ever load, unconditionally.
Confirmed this is live in production via PR #72's `krrood` CI leg failing on
`test_fit_scrdr` with the exact `IPythonShell.run()` infinite-retry symptom from #71.
Asked the user how to handle this scope expansion (AskUserQuestion) - approved "fix
both in this PR, as separated commits."

## Done

1. Fixed the delimiter mismatch: corrected the 8 committed fixture files back to
   single-quote delimiters matching `experts.py`. Commit `b253535`.
2. Fixed the race: added `isolated_expert_answers_path()` context manager in
   `helpers.py` that copies the committed fixture into a private temp dir; the three
   `get_fit_*` helpers now point `Human`'s `answers_save_path` at the isolated copy
   instead of the shared file. `save_answers=True` still targets the real committed
   path (unaffected). Commit `4b22ef4`.
3. TDD: added `test_expert_answers_isolation.py` (unit tests on the isolation
   mechanism, including an 8-thread concurrent stress test) and an integration test in
   `test_rdr_alchemy.py` (`test_get_fit_scrdr_does_not_mutate_committed_expert_answers_fixture`,
   using a 3-case slice). Both confirmed to fail pre-fix.
4. Verified locally: isolation unit tests pass deterministically; small-slice
   integration test passes and provably failed pre-fix; broader
   `test_ripple_down_rules` suite (excluding full-dataset fit tests) passes with no
   regressions (26 passed, 6 skipped, same as before); collection of the whole
   `test_ripple_down_rules` directory succeeds cleanly (79 tests, no import errors).
5. Could NOT get the *full* 101-case `test_fit_scrdr`/`test_fit_mcrdr_stop_only` to
   pass locally even post-fix - sandbox has no persistent zoo-dataset cache, live
   UCI fetch content/order apparently doesn't match what the fixtures were recorded
   against, so recorded answers run out partway through (same issue reproduces for
   unrelated `test_rdr.py` Animal-domain tests too). Documented as a caveat in the PR
   - this is a local-only reproducibility gap, not something the two fixes above
   cause or could fix; PR depends on CI to confirm the full-dataset tests.
6. Opened draft PR #73 against `main`, labeled `bug`, session link included,
   subscribed to PR activity.

## Done (continued)

7. First CI run confirmed my local finding was real, not a sandbox artifact: the
   `krrood` leg genuinely hung on the live job (`IPythonShell.run()`'s old infinite
   retry loop, same as before #71's fix) - user caught it ("that is too long...
   there's a loop hanging"). Cancelled the wasted run
   (`actions_run_trigger cancel_workflow_run`, run 29433858569).
8. PR #71 merged into `main` while I was investigating. Merged updated `main`
   (with #71's fix) into this branch - clean merge, no conflicts, commit `2e6dfad`.
   Pushed; new CI run in progress. This won't fix the "answers insufficient" issue
   itself but means CI will fail fast instead of hanging if it recurs, giving a real
   signal instead of burning 40+ min per run.
9. Commented on PR #73 explaining the cancellation + merge.

## Next

- Watching the NEW CI run on PR #73 (post-#71-merge) - this is the real test of
  whether `test_fit_scrdr`/`test_fit_mcrdr_stop_only`/`test_fit_grdr` actually pass,
  or whether they now fail fast with `NonInteractiveTerminalError` (meaning the
  "answers insufficient" issue is real in CI too and needs further investigation
  beyond the two fixes already in this PR).
- If it fails fast with NonInteractiveTerminalError: this would mean the delimiter +
  isolation fixes are necessary but not sufficient - the recorded expert answers
  fixtures may need actual regeneration against current dataset content, which
  needs the user's input (domain-specific, can't safely guess correct RDR
  refinement conditions for zoo animal classification).
- Also still watching PR #72 (giskardpy race fix) - separate branch-keyed progress
  file, not duplicated here.

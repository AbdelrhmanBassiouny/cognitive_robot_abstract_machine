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

## Done (continued 2)

10. New CI run (post #71-merge) completed in 2:32 (not 40+ min) - confirms the
    fail-fast-instead-of-hang fix works. Result: 1697 passed, 9 skipped, 4 failed -
    all 4 failures are `NonInteractiveTerminalError` (not `FileNotFoundError`, not a
    hang): `test_rdr.py::TestRDR::test_fit_mcrdr_stop_only`,
    `test_rdr_alchemy.py::TestAlchemyRDR::test_fit_grdr`/`test_fit_mcrdr_stop_only`/
    `test_fit_scrdr`. My own regression tests (isolation mechanism unit tests +
    `test_get_fit_scrdr_does_not_mutate_committed_expert_answers_fixture`) are NOT
    among the failures - they pass in real CI too.
11. This confirms, with real CI evidence (not just local sandbox behavior): the
    delimiter fix and the race/isolation fix both genuinely work - no more
    FileNotFoundError, no more hangs. But the "answers insufficient" issue (recorded
    expert-answer fixtures don't have enough refinements for the current dataset
    content) is REAL in production CI too, not a local-only gap as I'd hoped/assumed
    in the PR caveat. This is a third, separate, now-confirmed-live issue.
12. This needs the user's domain judgment (correct RDR refinement conditions for
    zoo animal classification) - I should not guess/invent expert answers myself.
    Posting a clear summary to the PR and asking the user how to proceed (regenerate
    fixtures interactively themselves, investigate dataset content drift, accept as
    known follow-up, etc.) rather than attempting a fix.

## Next

- Awaiting user direction on the "answers insufficient" issue (see #12 above) -
  this PR's two original fixes (delimiter + race) are confirmed working via real CI
  evidence; whether to also try to address the third issue in this PR or split it
  off depends on what the user wants.
- Also still watching PR #72 (giskardpy race fix) - separate branch-keyed progress
  file, not duplicated here.

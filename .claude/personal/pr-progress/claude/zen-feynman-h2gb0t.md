## A branch under upstream review is only pushed inside a push window

PR: https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/437
(draft, base `main`) - and now also carried on `integration` as 8927b828dc.

**Ask**: a restack must not push a branch with an open upstream pull request
unless it is night in Berlin and 4 hours have passed since its last push. A
manual run pushes anyway.

### Done
- `push_window.py` (`PushWindow`, `WaitReason`), `stack.toml` settings,
  `committed_at`, `HoldBranchUnderReview` in `RESTACK_STEPS`,
  `RestackOutcome.HELD`, `--push-branches-under-review-now` on `restack` and
  `run-report`, docs. 176 tests on the `main`-based branch.
- Ported onto `integration` by cherry-pick (six conflicts, all in these files).
  On that branch `GitCommandRunner` lives in `.claude/shared/git_commands.py`,
  so `committed_at` went there; `maintenance_git_commands.py` keeps only what a
  pass adds.
- `integration_selection.py`'s `restack(...)` now passes `push_window=None` -
  `integration.py build --restack` observes no window, which closes the item
  left outstanding last session.
- `.claude/stack/tests` on the ported integration branch: 527 pass. The 4
  `test_integration_reproduction.py` failures are pre-existing and fail
  identically on clean `origin/integration`.

### Findings for the user
- Stale `in-review` labels, checked against upstream by git (no merge ref while
  the branch merges `cram2/main` cleanly => the upstream PR is closed):
  **stale**: #248 (upstream #654), #261 (#647), #262 (#661), #264 (#656).
  **still open upstream**: #229 (#655), #251 (#653), #269 (#645).
  Not cleared - clearing puts those four back in the promotion queue, and why
  they were closed upstream is the user's to say.
- Asked whether to automate the label; proposed as its own PR (a fork Action
  reading upstream with GITHUB_TOKEN, as `upstream-reviews.yml` already does).

### Next
- Waiting on the user: clear the four stale labels? build the label automation?

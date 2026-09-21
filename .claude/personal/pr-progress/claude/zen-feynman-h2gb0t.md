## A branch under upstream review is only pushed inside a push window

PR: https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/437
(draft, base `main`)

**Ask** (this session): a restack must not push a branch that has an open
upstream pull request unless it is night in Berlin and at least 4 hours have
passed since that branch was last pushed. A manual run pushes anyway.

**Base**: re-cut from `origin/main`. The branch arrived descending from
`integration` (274 commits, not a legal PR base). Every file this touches is on
`main`; the integration tooling (`integration*.py`) is on no open PR, so there
was nothing to stack on.

### Done
- `push_window.py`: `PushWindow` + `WaitReason`, pure, imports nothing else of
  the workflow's so `Configuration` can hold one.
- `stack.toml`: `review_push_night_begins/ends/time_zone/hours_between_pushes`
  (22:00-06:00 Europe/Berlin, 4h).
- `GitCommandRunner.committed_at` - when the fork's copy of a branch last moved.
- `HoldBranchUnderReview` in `RESTACK_STEPS`, after `SkipBranchAlreadyCurrent`
  and before `IntegrateParent`; `RestackOutcome.HELD`, excluded from the
  outcomes a pass needs attention for.
- `restack()` takes a required `push_window`; `--push-branches-under-review-now`
  on `restack` and `run-report`; routine prompt says to leave it off.
- SKILL.md and the stack README say when a promoted branch moves.
- 176 stack tests pass; 4 hook tests fail for missing dashboard dependencies in
  this container and fail identically on clean `main`.

### Outstanding
- `integration.py build --restack` calls the shared `restack()`, so it inherits
  the window - but its call site lives on no open PR, so its
  `push_window=None` (push whatever the hour, per the decision made here) has to
  be added by whichever PR eventually lands that tooling. Nothing to do on this
  branch.
- Nothing else. Waiting on review.

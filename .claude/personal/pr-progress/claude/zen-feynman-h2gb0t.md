## A branch under upstream review is only pushed inside a push window

**Ask** (this session): a restack must not push a branch that has an open
upstream pull request unless (a) it is night in Berlin and (b) at least 4 hours
have passed since that branch was last pushed. A manual run pushes anyway.

**Base**: re-cut from `origin/main`. The branch arrived descending from
`integration` (274 commits, not a legal PR base). Every file this touches is on
`main`; the integration tooling (`integration*.py`) is on no open PR, so there
was nothing to stack on.

**Where it lands**: `maintenance.py restack` and `integration.py build
--restack` both run `maintenance_restack_procedure.RESTACK_STEPS`, so one new
step covers both surfaces.

### Plan
1. `push_window.py`: `PushWindow` (night begins/ends, time zone, least time
   between pushes) + `WaitReason`. Pure, imports nothing of ours.
2. `Configuration` gains `push_window`; `stack.toml` gains its four defaults
   (22:00-06:00 Europe/Berlin, 4 hours).
3. `GitCommandRunner.committed_at` - when the fork's copy of a branch last moved.
4. `HoldBranchUnderReview` step, after `SkipBranchAlreadyCurrent` and before
   `IntegrateParent`; new `RestackOutcome.HELD`, which is not a branch needing
   attention.
5. `restack()` takes `push_window: PushWindow | None` (required; `None` = push
   whatever the hour). `--push-branches-under-review-now` on `restack` and
   `run-report`.
6. Skill + README say when a promoted branch moves.

### Done
- Investigation, base decision, design settled with the user (clock = last
  push; night = 22:00-06:00 Berlin; override = its own flag).

### Next
- Write the failing tests, then implement 1-6, then push and open the draft PR.

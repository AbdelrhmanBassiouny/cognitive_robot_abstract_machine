PR #211 - `integration-branch-ci-verdict` and `red-candidate-localisation` of
`stack-maintenance`. Resolved via `/plan-item-resolve` in auto mode.

## Plan for this session

Both threads the 2026-08-30 round left open had been answered by the author
overnight, so the item was not blocked on anything outside itself:

1. The repeated docstring - clarified as the check timing, not the `sys.path`
   insertion. Single-source it.
2. The rebuild cadence - "I like the fix, fold or new item?". Run the scope
   check, recommend, act.

## Done

- Manifest blockers rewritten to the real state before any code was touched,
  then cleared once both were resolved; roadmap gained two rules and its
  queue-delay risk was corrected.
- `CandidateCheckTiming` in `integration_verdict.py` holds the measurement;
  the four designs that restated it refer to it. Two tests, both reading the
  record.
- `workflow_run` trigger on CI completing over a build branch, folded here
  because `git ls-tree origin/main` over every file it touches is empty.
  `WorkflowDocument` gained `name`, `watched_workflows`, `branches`;
  `BUILD_BRANCH_FILTER` is spelled apart from `BUILD_BRANCH_PATTERN`.
- 913 tests pass (from 907), six mutations checked, formatter idempotent.
  Pushed as `e61f0a9c1`; PR description updated; the docstring thread replied
  to and resolved, the cadence thread replied to and left open.

## Outstanding

- The cadence thread is deliberately open: the author asked a question and
  should close it themselves.
- A `workflow_dispatch` of `Integration refresh` was run on this branch, which
  is the bootstrap that gets the new pipeline onto the default branch - a
  `workflow_run` trigger is read from the published copy, so it does nothing
  until a build carrying it publishes.
- Not re-drafted, deliberately: a draft is excluded from every build.

## 2026-08-30 late: the pipeline must not be allowed to publish yet

Verification candidate #224 (build against `main`) came back green on all 23
checks, and the build was **not** published. It carries nine branches and
neither #154 nor #211, so it holds no `integration.py` and no
`integration-refresh.yml` - publishing it onto `integration`, the default
branch a schedule registers from, would have deleted the scheduled workflow
and every means of publishing a later build.

Cause of the omission: #211 conflicts with #160's branch over
`plan_item_bootstrap.py`, so the build skips it, and it is the tip carrying
#154. The fold this plan already decided on is what clears it.

#220 and #224 both closed. Manifest, roadmap and dashboard record the hazard.

Order the remaining work has to happen in: guard against publishing a build
that would remove the pipeline, *then* make candidates judgeable (base +
discriminator), *then* fold #160. Doing the second before the first is what
turns the first checkable green build into the one that ends the automation.

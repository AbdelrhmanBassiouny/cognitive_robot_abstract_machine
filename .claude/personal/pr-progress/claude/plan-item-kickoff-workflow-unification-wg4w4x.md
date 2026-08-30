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

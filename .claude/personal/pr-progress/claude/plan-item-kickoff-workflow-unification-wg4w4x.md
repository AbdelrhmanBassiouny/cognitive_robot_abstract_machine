# PR #211 - `integration-branch-ci-verdict` + `red-candidate-localisation`

Two plan items share this branch, both in `stack-maintenance`. This session resolved
`integration-branch-ci-verdict` via `/plan-item-resolve` (auto mode).

## What was stalling it

A six-thread review round submitted 2026-08-30T09:48Z against the branch's own head
commit `8227ef57`, unanswered. CI green on all 25 checks, `clean`, out of draft - nothing
else held it, and the manifest recorded no blocker at all.

## Done

- `7d9ba6f6d` - `take-down-unreferenced-builds` (the eight stranded `integration-*`
  branches), the one pull-request-record builder across tests and the production client,
  the workflow model growth (`WorkflowInput`, `ActivityType`, `variable`/`passes`,
  `OptionalArgument`), `file_names_in` + `remote_branch_names` on the runner.
- `b08badf05` - moved `test_integration_verdict.py`'s raw-YAML section onto the model
  (`test_integration_verdict.py` 742 -> 618 lines), `PassedArgument`, `CheckoutInput`,
  `GitHubContext` additions.
- Six threads answered; four resolved. PR description brought up to date - it had no
  section for `8227ef57` at all.
- Manifest + roadmap saved (`2cd57b1ae`), dashboard republished, tracking issue #102
  updated with the structural split.
- 907 tests pass across the four directories CI runs, from 899. Nine mutations checked.

## Outstanding - both are the author's call, and both are why the item still carries a blocker

1. **The repeated `"shared"`** (thread on `integration_pipeline.py`). It is the `sys.path`
   insertion in 18 files across three directories. Answered with `bastler-package` (#185),
   which removes all 18 by name. If the author wants the three-constant version now, it is
   a small change.
2. **The rebuild cadence** (thread on `integration_pipeline.py`). A first-time build is
   judged by a later run, up to six hours away. Proposed fix is a `workflow_run` trigger
   on `ci.yml` completing, filtered to `integration-*`; it adds a trigger, so it was not
   made unilaterally. Asked whether it belongs in this PR or its own item.
3. **The dashboard integrate control** (thread on `integration-refresh.yml`). Four asks;
   two already shipped, two need items on `plan-dashboards`. Proposed on #102, not created.

## Not to do

- **Do not re-draft this PR after pushing.** The item's notes record that it stays out of
  draft deliberately - a draft is excluded from every integration build.
- No PR-activity subscription, and no scheduled check-ins.

## Next, if asked

Whichever of the three above the author picks. Nothing else is outstanding on the branch.

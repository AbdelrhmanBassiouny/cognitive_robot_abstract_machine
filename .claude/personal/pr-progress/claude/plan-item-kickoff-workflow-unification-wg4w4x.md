# red-candidate-localisation — PR #211 (draft), on #154

Plan item `red-candidate-localisation` of `workflow-unification`, `stack-tooling`
track. Branch `claude/plan-item-kickoff-workflow-unification-wg4w4x`, based on
`claude/plan-item-kickoff-workflow-ixbvxl` (#154). Kickoff in `auto` mode,
session https://claude.ai/code/session_0138w5mqzbkyMPtotF7PD59Z.

## What it does

A candidate red on a matrix job names a failing check and nothing else.
`block-branch` cannot localise it — it re-runs the four tooling directories, and
`test_each_lib (<lib>)` lives in the docker matrix. This re-runs the failing
library's own job over each prefix of the merge order and reports which tip's
arrival turned it, as the same `IntegrationTestFailure` the local search
produces.

## Built (all six steps)

1. **`ci_reusable.yml`** — optional `ref` input, defaulting to what
   `actions/checkout` already does with none, so every existing caller is
   unchanged.
2. **`.github/workflows/integration-probe.yml`** — `workflow_dispatch` over
   `build` + `library`, calling `ci_reusable.yml`; `run-name` names the tree.
3. **`maintenance_github.py`** — `DispatchedWorkflowRuns`, declared apart from
   the pull-request surfaces; `_call` now tolerates the 204 a dispatch answers.
4. **`integration_localisation.py`** — probes, verdicts, the two rounds, the
   state document, and which failing checks this owns.
5. **`integration.py`** — `ProbeAssembly` beside `FailureLocation`, and the
   `locate-candidate-failure` subcommand with statuses 15 and 16.
6. **`integration-refresh.yml`** — runs it when a candidate comes back red.

## Settled at kickoff (full reasoning in the plan's roadmap.md)

- Only a failed check naming a library is this search's.
- Probes are dispatched on the reference carrying the pipeline, not on the
  prefix — a prefix starts from upstream `main` and carries no workflow.
- Correlation is by `run-name`; a probe whose run has not appeared reads as
  waiting rather than `ABSENT`-and-wrong.
- One repeatable subcommand over a state document; the waiting stays with the
  caller.
- Linear scan, dispatched in parallel — one run's wall clock, no monotonicity
  assumed.
- The narrowing round is built, not deferred.

## Found while building

- **The two rounds could collide on a probe branch name** when both calls land
  in the same second, so a narrowing probe would be answered by the run that
  judged a prefix. The name carries its round now; pinned by a test.
- **A contract test over a workflow has to search the right executable
  surface.** Asserting status `14` against the step's shell passed nothing —
  it lives in the step's `if:`. Split into two rules, each failing for its own.

## Verified

- 798 tests pass across the four directories CI runs, from 758.
- Five mutations checked, each caught by exactly the test naming its rule:
  the library selection, the probe branch naming, the narrowing order, the
  narrowing round being opened, and the take-down on conclude.
- `format_docstrings.py` is a no-op on the new module and re-running it returns
  it byte-identical.

## Known limit

The end-to-end live run is gated on a build carrying this branch — a
`workflow_dispatch` workflow is only dispatchable once it is on the default
branch. Same bootstrap Part D needed on 2026-08-28. Stated, not closed.

## Next

Nothing outstanding on the branch. Awaiting review.

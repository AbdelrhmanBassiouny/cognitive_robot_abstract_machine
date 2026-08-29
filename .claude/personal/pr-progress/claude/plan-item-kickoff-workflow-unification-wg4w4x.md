# red-candidate-localisation — PR #211 (draft), on #154

Plan item `red-candidate-localisation` of `workflow-unification`, `stack-tooling`
track. Branch `claude/plan-item-kickoff-workflow-unification-wg4w4x`, based on
`claude/plan-item-kickoff-workflow-ixbvxl` (#154). Kickoff in `auto` mode,
session https://claude.ai/code/session_0138w5mqzbkyMPtotF7PD59Z.

## What it does

A candidate that comes back red on a matrix job names a failing check and
nothing else. `block-branch` cannot localise it — it re-runs the four tooling
directories, and `test_each_lib (<lib>)` lives in the docker matrix. This
re-runs the failing library's own job over each prefix of the merge order and
reports which tip's arrival turned it.

## Settled at kickoff (full reasoning in the plan's roadmap.md)

- **Which checks this owns.** Only a failed check naming a library.
  `test_claude_dev_tooling` is already localised locally by `block-branch`, and
  `check_generated_orm_interfaces_are_untracked` is a property of one tree.
  Say so plainly when no failing check names a library.
- **Probes are dispatched on the default branch, not on the prefix.** A prefix
  starts from upstream `main` and carries no probe workflow; the empty prefix
  never will. The tree to test is an input, which needs one optional `ref`
  input on `ci_reusable.yml`.
- **Correlation is by `run-name`**, since a dispatch answers 204 with no run
  id and every probe shares a ref. A probe whose run has not appeared yet reads
  as running, not `ABSENT`.
- **One repeatable subcommand over a state document**, the way
  `settle-candidate` is one read; the waiting stays with the caller.
- **Linear scan, dispatched in parallel** — one run's wall clock for N probes,
  and no monotonicity assumed, which a bisection would need.
- **The narrowing round is built, not deferred**: `breaks_against=None` is a
  positive claim ("no single earlier tip reproduces it alone") that an
  un-narrowed report would make without checking.
- **Reuse the finding**: produce the same `IntegrationTestFailure` and block
  through the same `block_the_branch_that_causes_it`.

## Plan

1. `ci_reusable.yml`: optional `ref` input. Test asserts the probe workflow
   passes it. *(not started)*
2. `.github/workflows/integration-probe.yml`: `workflow_dispatch` over
   `library` + `build`, calling `ci_reusable.yml`; `run-name` names the tree.
   Contract tests for every name the workflow retypes. *(not started)*
3. `maintenance_github.py`: an Actions surface — dispatch a workflow, list a
   workflow's runs — as its own ABC beside `CandidatePullRequests`.
   *(not started)*
4. `integration_localisation.py`: prefixes, probes, the two rounds, the state
   document, the report. Reuses `ChecksVerdict`, `tips_of`, `IntegrationBuild`
   and `IntegrationTestFailure`. *(not started)*
5. `integration.py`: `locate-candidate-failure` subcommand and its exit codes.
   *(not started)*
6. `integration-refresh.yml`: run it when a candidate comes back red.
   *(not started)*

TDD throughout: each step's test first. Verified in-harness against a fake
client and a scratch repository.

## Known limit

The end-to-end live run is gated on a build carrying this branch — a
`workflow_dispatch` workflow is only dispatchable once it is on the default
branch. Same bootstrap Part D needed on 2026-08-28. Stated, not closed.

## Next

Step 1.


# claude/integration-status-tooling-prs-1bsk40 - PR #291

## What this branch is

`Carry on when the fork refuses to record a pass`. Based on #211
(`claude/plan-item-kickoff-workflow-unification-wg4w4x`), the branch that introduces the
pass record. Draft, labelled `bug` + `tooling`.

`PassedChecks.record` wrote through `git.run`, which raises, so a fork refusing the push
into `refs/integration/*` ended the run with `git-command-failed (6)` before assembly
began. A session credential is refused there (HTTP 403), so `integration.py build` could
not be run from a session at all. It now writes through `git.attempt`: a refused write
costs the reuse, says so on stderr, and leaves the set as it stood.

Diff is 3 files, +93/-3: `bastler/integration_pass_record.py`,
`test/bastler_test/test_integration_pass_record.py` (three new tests, all failing against
the old code), `test/bastler_test/test_integration_selection.py` (the `attempt` seam on
`GitWithOneBranchPublished`).

## 2026-09-08: conflict and CI pass

- The base landed the `.claude/` -> `bastler/` relocation, so #291 was `dirty`. Merged the
  base in (`1a3f3b7380`). One conflict: the import line in `test_integration_selection.py`
  - my `GitCommandResult` addition against the base's `bastler.` package prefix. Resolved
  to `from bastler.git_commands import GitCommandResult, ReferenceUpdate`. Everything else
  auto-merged; git carried the renames, so the diff is unchanged at +93/-3.
- `python -m pytest test/bastler_test --confcutdir=test/bastler_test`: **1160 passed**.
  (The tooling CI job is now `test_bastler`, not `test_claude_dev_tooling`.)
- `mergeable_state` went `dirty` -> `unstable`. Cleared `needs-resolution`, re-drafted,
  updated the description's stale `.claude/stack/tests/` paths.

## The red check on #291 is not #291's

`Rebuild the integration branch and publish it if it is green` (run 59, event
`pull_request`/`ready_for_review`) failed `tests-failed (11)`. It is the fork-wide
integration rebuild, and #291's own tip was **skipped** from that build - the tree that
failed does not contain this commit. It is also in `PIPELINE_WORKFLOWS`, so the build's own
selection does not count it against a branch. Same failure as every scheduled refresh since
2026-09-05.

Two things worth knowing about it:
- `integration_suite.run_tests` uses `capture_output=True` and discards the output, so a
  failing integration suite reports `tests-failed` with no diagnostic in the job log at all.
- `bastler/stack.toml`'s `integration_test_command` still reads
  `.claude/skills/plan-dashboard/tests .claude/hooks/tests .claude/stack/tests`. After the
  relocation that last path is gone, so any build carrying the relocation tip errors out of
  pytest before running anything. On this run the relocation was not among the merged tips,
  so that is a second latent failure rather than this one's cause.

Neither is #291's to fix - both live on the base/relocation chain.

## Findings from the integration-status pass (not acted on)

1. The scheduled Integration refresh has been red since at least 2026-09-05, every run
   exit 11, and `integration` has not moved since 2026-09-01. #285 fixes the pipeline-loss
   half; it is open, ready, green, and now labelled `tooling`.
2. The tooling integration is blocked on the half-finished relocation: with the relocation
   chain in, 14 of 16 tooling tips are skipped; held out, 6 tips merge (carrying 9 pull
   requests) and 7 sibling conflicts remain.
3. #281, #282, #284, #285 belong to no plan, so a `--plan` build reports them
   `no-plan-recorded` and leaves them out.
4. #280 is red on `BRANCH_NEEDS_ATTENTION (10)`: the pass ran fine and reported 9 branches
   withheld as "still conflicted against its base since a previous pass", none of them
   #280's. `stack-maintenance.yml` is not in `PIPELINE_WORKFLOWS`, so the build reads that
   stack-wide verdict as ordinary CI on #280 and drops it.
5. `integration.py build` does not set up the upstream remote the way `refresh`'s `_prepare`
   does, so a fresh clone fails with `git-command-failed (6)` on `git fetch cram2`.

## Published

`claude/tooling-integration-20260906` - the best tooling build (base `cram2/main`, the
relocation chain held out). 630 tooling tests pass on it. Named outside `integration-*` so
`take-down-unreferenced-builds` does not sweep it.

## Next

Nothing outstanding on #291 itself beyond the CI run in flight. Findings 1-5 were handed
back as prompts.


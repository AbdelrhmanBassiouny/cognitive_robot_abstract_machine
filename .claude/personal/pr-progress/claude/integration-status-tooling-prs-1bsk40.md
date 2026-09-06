# claude/integration-status-tooling-prs-1bsk40 - PR #291

## What this branch is

`Carry on when the fork refuses to record a pass`. Based on #211
(`claude/plan-item-kickoff-workflow-unification-wg4w4x`), the branch that introduces
`integration_pass_record.py`. Draft, labelled `bug` + `tooling`.

`PassedChecks.record` wrote through `git.run`, which raises, so a fork refusing the push
into `refs/integration/*` ended the run with `git-command-failed (6)` before assembly
began. A session credential is refused there (HTTP 403), so `integration.py build` could
not be run from a session at all. It now writes through `git.attempt`: a refused write
costs the reuse, says so on stderr, and leaves the set as it stood.

Tests: three in `test_integration_pass_record.py` against the scratch fork with a
`pre-receive` hook rejecting the record namespace; all three fail against the old code.
`GitWithOneBranchPublished` gained the `attempt` seam. Full tooling suite 1018 passed.

## Why the branch exists

Asked to report integration status and get every open ready tooling pull request carried
by an integration build. This fix was what stood between a session and running the build
at all.

## Findings (not yet acted on)

1. **The scheduled Integration refresh has been red since at least 2026-09-05**, every
   run exit 11, and `integration` has not moved since 2026-09-01. Root cause is the
   `.claude/` -> `bastler/` relocation decapitating the pipeline mid-build. #285 fixes
   it; it is open, ready, green, and now labelled `tooling` (it was not - the only
   mislabelled pull request on the fork, checked with #284's own classifier).
2. **The tooling integration is blocked on the half-finished relocation.** With the
   relocation chain in, 14 of 16 tooling tips are skipped; with it held out, 6 tips
   merge (carrying 9 pull requests) and 7 sibling conflicts remain. Every skip in the
   first case is a `.claude/` <-> `bastler/`/`test/bastler_test/` pair.
3. **#281, #282, #284, #285 belong to no plan**, so a `--plan` build reports them
   `no-plan-recorded` and leaves them out.
4. **#280 is red on `BRANCH_NEEDS_ATTENTION (10)`** - the maintenance pass ran fine and
   reported branches needing attention. A design question, not broken code.
5. `integration.py build` does not set up the upstream remote the way `refresh` does, so
   a fresh clone fails with `git-command-failed (6)` on `git fetch cram2`.

## Published

`claude/tooling-integration-20260906` - the best tooling build (base `cram2/main`, the
relocation chain held out). 630 tooling tests pass on it. Named outside `integration-*`
so `take-down-unreferenced-builds` does not sweep it.

## Next

Nothing outstanding on #291 itself. Findings 2-5 were handed back as prompts.

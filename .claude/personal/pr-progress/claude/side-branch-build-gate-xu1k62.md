# PR #425 - side-branch build gate

Every integration candidate dies on `Run the maintenance pass`, from
`stack-maintenance.yml` (#280), which a build carries and which GitHub therefore
runs on the candidate itself. It judges the whole fork (a branch withheld as
conflicted -> exit 10) and `PIPELINE_WORKFLOWS` did not exclude it, so
`ChecksVerdict` answered FAILED before the matrix finished.

## Plan
- Add `INTEGRATION_CHECKS` and `STACK_MAINTENANCE` to `WorkflowFile` and to
  `PIPELINE_WORKFLOWS`, so neither votes on a build.
- Read past a pipeline workflow this checkout does not hold, since no tree today
  carries both `bastler/integration_verdict.py` (#211) and `stack-maintenance.yml`
  (#280) and `.read()` would otherwise crash the whole rebuild.

## Done
- Branch re-cut from #211's head (`claude/plan-item-kickoff-workflow-unification-wg4w4x`),
  which owns the verdict module; PR #425 opened as a draft against it, labelled `bug`.
- Three tests written failing first, then the fix. Full suite: 1164 passed.
- `WorkflowFile`'s file-exists invariant narrowed to exempt the pipeline's own
  workflows, with the reason recorded in the test docstring.

## Decisions
- Asked before starting; chose "relax the file-exists invariant on #211" over
  merging #280 in (its `.claude/stack/` -> `bastler/` relocation conflicts on six
  files - that resolution belongs to the integration build, not to this fix).
- Stacked rather than folded into #211 because this session is pinned to its own
  branch. It is a fold candidate if you would rather squash it into #211.

## Next
- Nothing outstanding in this session. CI on #425 was left unwatched by standing
  preference.
- The fix only bites from a checkout holding `stack-maintenance.yml`; today's
  `integration` pointer does not. First pass needs a `workflow_dispatch` of the
  refresh on a ref carrying both, or the first publish after #280 lands.
- Open question if the gate needs to close without that: read the workflow out of
  the tree the checks were reported against instead of out of the tooling's
  checkout. Larger change, not attempted.

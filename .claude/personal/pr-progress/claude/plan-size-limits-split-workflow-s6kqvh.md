# plan-size-limits / split-workflow-unification

No branch and no pull request: personal-notes data only, per the item's own notes and the
`eql-roadmap-migration` precedent. This branch stays empty.

## Outcome

`workflow-unification` (59 items, 5,129 manifest + 11,788 roadmap = 16,917 lines) is replaced by
seven plans, pushed to the notes branch in one commit (`e69094af3`). Measured live afterwards:

| new plan | items | lines |
|---|---|---|
| `stack-tooling-install` | 7 | 435 |
| `stack-maintenance` | 11 | 737 |
| `plan-tracking-skills` | 6 | 299 |
| `session-notes-infrastructure` | 10 | 415 |
| `plan-dashboards` | 12 | 419 |
| `bastler-package` | 10 | 413 |
| `workflow-cutover` | 3 | 198 |

16,917 lines to 2,916, all within the 15-item / 2,000-line budget. `rdr-refactor` is the only plan
still over, which is the sibling item `split-rdr-refactor`.

Rules applied (full reasoning in `plan-size-limits/roadmap.md`):
- Items keep `branch`, `pull_request_number`, `status`, `session` verbatim; all 59 accounted for
  once, checked mechanically, and every manifest passes `build_dashboard.validate_plan`.
- `depends_on` cannot cross a plan (`UnknownDependency` is fatal): five edges onto merged items
  dropped into `notes`, three live ones recorded as `blockers`.
- Roadmaps rewritten rather than sliced. The 11,788-line original stays in the notes branch's
  history.
- All seven keep `tracking_issue: 102`.
- Branch index regenerated; `workflow-unification`'s cached dashboard URL dropped.

## Done

- Context gathered; dependency `size-budget-and-report` (#207) confirmed ready.
- Kickoff plan recorded in `plan-size-limits/roadmap.md`.
- Seven manifests and roadmaps built, validated, and pushed.
- Old plan directory deleted; index and URL cache updated in the same commit.

## Next

1. Publish the seven dashboards and refresh the master index.
2. Comment the split on tracking issue #102.
3. Mark the item `done` and republish `plan-size-limits`' dashboard.

## Left alone deliberately

`_generated/branch-index.yaml` still names `workflow-unification`. Nothing reads it - `save-plan.sh`
regenerates only the `.tsv`, and a grep of `.claude/` finds no reader - so it is a dead generated
file that predates this work, and deleting it is outside this item.


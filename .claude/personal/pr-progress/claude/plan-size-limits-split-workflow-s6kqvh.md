# plan-size-limits / split-workflow-unification

No branch and no pull request: personal-notes data only, per the item's own notes and the
`eql-roadmap-migration` precedent. This branch stays empty.

## Plan

Split `workflow-unification` (59 items, 5,129 manifest + 11,788 roadmap = 16,917 lines)
into seven plans, each under the 15-item / 2,000-line budget:

| new plan | items | source |
|---|---|---|
| `stack-tooling-install` | 7 | stack-tooling (install half) |
| `stack-maintenance` | 11 | stack-tooling (pass half) |
| `plan-tracking-skills` | 6 | personal-data (plan-item skills) |
| `session-notes-infrastructure` | 10 | personal-data (session/notes half) |
| `plan-dashboards` | 12 | dashboards, unchanged |
| `bastler-package` | 10 | bastler, unchanged |
| `workflow-cutover` | 3 | cutover, unchanged |

Rules settled at kickoff (full reasoning in `plan-size-limits/roadmap.md`):
- Items keep `branch`, `pull_request_number`, `status`, `session` verbatim.
- `depends_on` cannot cross a plan (`UnknownDependency` is fatal): five edges onto `done`
  items are dropped into `notes`; three live ones demote to `blockers`.
- Each successor roadmap is rewritten, not sliced — keep decisions/hazards/open questions,
  compress merged items' narrative to their pull request link.
- All seven keep `tracking_issue: 102`.

## Done

- Context gathered; dependency `size-budget-and-report` (#207) confirmed ready.
- Measured the by-track split and found it insufficient — recorded in the roadmap.
- Kickoff plan recorded in `plan-size-limits/roadmap.md`; item is `in_progress`.

## Next

1. Build the seven `plan.yaml` manifests.
2. Write the seven `roadmap.md` files under budget.
3. Save each with `save-plan.sh`, verify with `plan-size-report.sh`.
4. Delete the `workflow-unification` directory and its `dashboard-urls.yaml` key.
5. Publish the seven dashboards and the master index; comment the split on issue #102.


# plan-size-limits / split-workflow-unification — done

No branch and no pull request: personal-notes data only, per the item's own notes and the
`eql-roadmap-migration` precedent. This session's designated branch stays empty.

## Outcome

`workflow-unification` (59 items, 5,129 manifest + 11,788 roadmap = 16,917 lines) is replaced by
seven plans. Item marked `done`; structural record on tracking issue #102.

| new plan | items | lines | dashboard |
|---|---|---|---|
| `stack-tooling-install` | 7 | 435 | 7681295b-a29c-41b8-9799-81eab81b4033 |
| `stack-maintenance` | 11 | 737 | c61f29b5-37a6-4498-a159-1b8c6a881d8a |
| `plan-tracking-skills` | 6 | 299 | 63aac9c6-66e1-485b-a40f-f5302cff054d |
| `session-notes-infrastructure` | 10 | 415 | a35f0207-226c-4a96-a766-c9c11638fb6c |
| `plan-dashboards` | 12 | 419 | a3b7aea9-cb03-4a5c-a57c-fe9c44581257 |
| `bastler-package` | 10 | 413 | 53c38b8e-e4ae-4dea-91a0-36a5faa78ccd |
| `workflow-cutover` | 3 | 198 | 2bfad2c4-a7a0-42a4-a6ea-f75ed043a8f4 |

16,917 lines to 2,916. Every plan in the directory is now within the 15-item / 2,000-line budget
except `rdr-refactor` (49 items, 4,282 lines), which is `split-rdr-refactor`.

## Commits on the notes branch

- `e69094af3` — the split itself: seven plan directories added, `workflow-unification` deleted,
  branch index regenerated, its dashboard URL key dropped, all in one commit.
- `273436cb9` — the seven new dashboard URLs recorded through `record_dashboard_url.py`.
- Plus the kickoff and outcome roadmap sections and the `done` status on `plan-size-limits`.

## How the move was checked rather than trusted

- All 59 items present exactly once, none invented — set comparison against the source manifest.
- Every successor passes `build_dashboard.validate_plan`.
- `branch`, `pull_request_number`, `status` and `session` copied field-for-field by the builder.
- All seven dashboards rendered against live GitHub with **zero drift flags**, which is the
  independent confirmation that no status changed in the move.

## Rules applied

- `depends_on` cannot cross a plan (`UnknownDependency` is fatal): five edges onto merged items
  dropped into `notes`, three live ones recorded as `blockers` (`shared-pr-state-chips` →
  `bastler-package`; `bastler-github-api-unification` → `setup-personal-notes-script` and →
  `shared-pr-state-chips`).
- Roadmaps rewritten, not sliced. The 11,788-line original is in the notes branch's history.
- All seven keep `tracking_issue: 102`.

## Nothing outstanding

The master index was refreshed too, since the plan list itself changed.

## Left alone deliberately

`_generated/branch-index.yaml` still names `workflow-unification`. Nothing reads it — `save-plan.sh`
regenerates only the `.tsv`, and a grep of `.claude/` finds no reader — so it is a dead generated
file predating this work, and deleting it is outside this item.


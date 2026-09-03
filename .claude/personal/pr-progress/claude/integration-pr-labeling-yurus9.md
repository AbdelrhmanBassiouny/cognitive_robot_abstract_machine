## Session purpose

`/add-plan-item`: decide where "label every pull request the integration branch
carries as `integrated`, and unlabel the ones it drops" belongs. Placement only —
this skill writes no code, opens no branch and opens no pull request.

## Outcome (approved)

A **new item** in the existing `stack-maintenance` plan, `integration` track:
`integrated-label`, stacked on #211.

Evidence: 7 of the 9 paths the work touches are absent from `main` (the whole
integration machinery is unlanded) and #211 shares all 9, so it stacks on #211
rather than branching off `main`. Not a fold, because stripping #211's files
still leaves a new subject — persisting a build's per-tip outcomes and
reconciling a label across every pull request the build considered — and it
stands alone once #211 lands. No duplicate intent: every existing label write
in the tooling is one branch, one subject.

Design decision taken by the user: labels are written **at publish**, not at
assemble, so `integrated` means "in the integration branch as it now stands".
That is what forces the persistence step — `RefreshPipeline.run` settles the
previous run's candidate before assembling this run's build, so the published
build's report is not in memory when the pointer moves.

## Done

- Setup: installed the plan-dashboard dependencies (`markdown`, `nh3`).
- Ran the scope check and the duplicate-intent scan; recorded the reasoning.
- Recorded `integrated-label` in `plan.yaml` (`not_started`, track `integration`)
  with its `roadmap.md` section, and set its `depends_on` to
  `integration-branch-ci-verdict` and `red-candidate-localisation`.
- Republished the `stack-maintenance` dashboard.

## Next

- Nothing on this branch. The item is tracked; work starts with
  `/plan-item-kickoff stack-maintenance integrated-label`, which must cut its
  branch from #211's head — **not** from this branch, which descends from
  `integration` and is not a valid pull request base.
- The master index (`/plan-dashboard` with no argument) was not refreshed; a new
  item changes no plan's presence in it, only its counts.

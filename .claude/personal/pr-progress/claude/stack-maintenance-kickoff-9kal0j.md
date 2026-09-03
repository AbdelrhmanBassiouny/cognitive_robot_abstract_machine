# integrated-label (stack-maintenance) - PR #260

Based on #211's branch `claude/plan-item-kickoff-workflow-unification-wg4w4x`; six of the nine
paths do not exist on `main`. Both dependencies are `open_ready` and both are #211.

## The plan

1. `.claude/stack/integration_integrated_label.py` (new) - the record and the reconciler.
   `INTEGRATED_RECORD_NAMESPACE = "refs/integration/carried"`; `IntegratedTipRecord`
   (build_branch, pull_request_number, commit) with `reference` / `named_by`;
   `IntegratedTipRecords` with `read`, `carried_by`, `record`, `forget`, `forget_taken_down`;
   `reconcile_integrated_label(...)` returning the writes it made.
2. `stack.py` - `DefaultLabel.INTEGRATED = "integrated"` plus `Configuration.integrated_label`.
   `load_configuration` derives the field name from the member, so nothing else changes.
3. `stack.toml` - the committed default and why the label exists.
4. `integration_build_commands.BuildCommand.run` - record the integrated tips of the report it
   just produced, unconditionally, keyed by `report.build_branch`.
5. `integration_candidate_commands` - call the reconciler from
   `SettleCandidateCommand._publish_what_passed` and `PublishRecordedPassCommand.run`, the two
   sites that reach `publish()`; print the writes to standard error.
6. `README.md` - the label in the workflow's own vocabulary.

## Design calls (recorded in roadmap.md)

- Reconcile to an exact set rather than persisting both sides of the outcome: that is what covers
  a pull request labelled by an earlier run and absent from this report.
- A build branch with no records reconciles nothing, the way `BlockStanding.UNRECORDED` works.
- Records are kept while their build branch is; the existing take-down rule clears them.
- No comment per labelled pull request - ten branches four times a day.

## Status

- [x] Context gathered, dependencies checked, scope check re-run against `origin/main`.
- [x] Branch, draft PR #260, manifest entry, roadmap section.
- [ ] Tests first: `test_integration_integrated_label.py`.
- [ ] The module, the label, the two call sites.
- [ ] Run `.claude/stack/tests` + `format_docstrings.py`; push; keep #260 a draft.

## Met and not fixed here

`plan_item_bootstrap`'s `open` writes item fields at four spaces where this manifest uses two, so
the manifest entry was written by hand. That is #151's fix.

# integrated-label (stack-maintenance) - PR #260

Based on #211's branch `claude/plan-item-kickoff-workflow-unification-wg4w4x`; six of the nine
paths do not exist on `main`. Both dependencies are `open_ready` and both are #211.

## What was built

- `.claude/stack/integration_integrated_label.py` (new) - `IntegratedTipRecord` /
  `IntegratedTipRecords` under `refs/integration/carried/<build branch>/<pull request>`, plus
  `reconcile_integrated_label`.
- `stack.py` - `DefaultLabel.INTEGRATED` and `Configuration.integrated_label`; `stack.toml` -
  the committed default and why it exists.
- `integration_build_commands.BuildCommand._record_what_it_carried` - records at assemble time.
- `integration_candidate_commands.publish` - reconciles the label after the pointer moves, and
  drops the records of builds the fork no longer carries.
- `README.md` - the label in the source-of-truth table and the integration section.

## Design calls (recorded in roadmap.md)

- Reconcile to an exact set rather than persisting both sides of the outcome: that is what covers
  a pull request labelled by an earlier run and absent from this report.
- A build nothing recorded reconciles nothing, the way `BlockStanding.UNRECORDED` works.
- Records are kept while their build branch is; publishing deletes it and the take-down handles
  the rest, so `forget_dropped_builds` needs no knowledge of how a run ended.
- **The reconciler is called from `publish()` itself, not from the two commands.** The roadmap
  said "one reconciler called from two sites"; `publish()` is the one function both sites reach,
  and the pipeline guard already lives there for the same stated reason. Same outcome, one seam.
- No comment per labelled pull request - ten branches four times a day.

## Status

- [x] Context gathered, dependencies checked, scope check re-run against `origin/main`.
- [x] Branch, draft PR #260, manifest entry, roadmap section, dashboard republished.
- [x] Tests first: 16 in `test_integration_integrated_label.py`, eight mutations checked.
- [x] The module, the label, the record, the reconciliation, the README.
- [x] `format_docstrings.py` on every touched Python file.
- [ ] Full tooling suite green, then push and leave #260 a draft.

## Worth flagging on the PR

- `integration.py build` now writes to the fork on every run (one reference per carried tip),
  where before it only wrote when a readmitted branch's block was lifted.
- `publish-recorded-pass` now needs a credential, because reconciling reads the fork's open pull
  requests. It only ever runs inside the pipeline, which provisions one.

## Met and not fixed here

`plan_item_bootstrap`'s `open` writes item fields at four spaces where this manifest uses two, so
the manifest entry was written by hand. That is #151's fix.

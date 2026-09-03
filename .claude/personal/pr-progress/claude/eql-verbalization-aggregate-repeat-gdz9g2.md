# eql-verbalization / aggregate-repeat-reduction-ignores-same-kind-siblings — PR #264

Branch `claude/eql-verbalization-aggregate-repeat-gdz9g2`, cut from `main`. Kicked off in
`auto` mode; the full rationale is in the plan's `roadmap.md` section
"aggregate-repeat-reduction: the settled plan (2026-09-03, PR #264)".

## The plan

A repeat mention of an aggregate shortens to its bare aggregation word (*"the sum"*), which
only identifies it while it is the only aggregate of its kind. Give the aggregate's noun
phrase a `referent_id` only when its aggregation names one aggregate, so a query selecting
two sums describes each in full at every mention.

## Done — the item's work is complete and pushed

- Reproduced both manifestations on `main` (no dependency on #196 — see the roadmap section).
- Six tests written first, all failing on the two ambiguity cases and the missing pre-scan
  state: `test/krrood_test/test_eql/test_verbalization/test_aggregate_reference.py`.
- `ReferringExpressions.shared_aggregations` + `_shared_aggregations` in
  `microplanning/referring.py`; `AggregatorRule.build` consults it in
  `grammar/aggregation/rules.py`. `CoreferenceProcessor`/`DistinguisherIndex` untouched.
- `test_eql/test_verbalization` 768 → 774 passed / 3 skipped, no existing expectation changed;
  `test_eql` 1291 passed / 3 skipped. `scripts/format_docstrings.py` applied.
- Commit `62853d466` pushed; draft PR #264 open, labelled `bug`, description matching the work.
- Manifest, roadmap and dashboard all current.

## Next

- Developer review. Nothing is outstanding on this branch: CI has not been read from this
  session, and no check-in is armed (personal notes forbid scheduled checks).

## Decisions worth knowing at review time

- **Full description, not a determiner.** *"another sum"* / *"the other sum"* was the other
  option the item's note left open; the developer had already asked for the full spelling on
  #196's thread r3919032569, and an aggregate is told apart by what it aggregates anyway.
- **The rule decides, not the coreference pass.** `AggregatorRule.build` is what opts an
  aggregate into reduction by giving it a `referent_id`. A guard in `CoreferenceProcessor`
  keyed on "is this noun shared" would also catch every variable in a same-noun group, whose
  reduced mentions are still identifying because P2's determiners tell the group apart.
- **Counted per aggregate node, not per structural signature.** Conservative and a no-op: two
  `sum(x)` nodes over one chain have different referent ids, so neither is ever a repeat of
  the other. Structural comparison lives in `_expression_signature`, which #196 is changing.
- **Tests in a new module.** `test_set_of_ranking.py` was the first choice, but #196 appends
  an `Invoice` mimic there with exactly the fields this needs — the two branches would have
  defined the same fixture. `check_scope_overlap.py` now reports no shared path with any open
  pull request.

## Watch out

- `plan_item_bootstrap.py open` is broken on `main` (four-space indent into a two-space
  manifest — PR #160's bug, closed unmerged). The manifest entry here was written by hand;
  do not trust `open`/`record` on this plan until that is fixed.
- Local test environment: `python3.12 -m venv` with `random_events`, `probabilistic_model`,
  `krrood` installed editable, plus `objgraph` and `docformatter`; run pytest with
  `--confcutdir=test/krrood_test` to skip the root `conftest.py`'s sdt imports. `test_typing`
  needs `mypy`, which is not installed there.

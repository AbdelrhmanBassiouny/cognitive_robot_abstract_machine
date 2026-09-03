# eql-verbalization / aggregate-repeat-reduction-ignores-same-kind-siblings — PR #264

Branch `claude/eql-verbalization-aggregate-repeat-gdz9g2`, cut from `main`. Kicked off in
`auto` mode; the full rationale is in the plan's `roadmap.md` section
"aggregate-repeat-reduction: the settled plan (2026-09-03, PR #264)".

## The plan

A repeat mention of an aggregate reduces to its bare aggregation word (*"the sum"*), which
only identifies it while it is the only aggregate of its kind. Give the aggregate's noun
phrase a `referent_id` only when its aggregation word names one aggregate, so a query
selecting two sums describes each in full at every mention.

1. Tests first, both failing: two end-to-end wordings in `test_set_of_ranking.py` (the
   ranked frame and the ordered-by trailer), and a unit test of the new pre-scan state in
   `test_coreference.py`.
2. `microplanning/referring.py` — `ReferringExpressions` records which aggregation words
   name more than one aggregate in the scanned expression.
3. `grammar/aggregation/rules.py` — `AggregatorRule.build` consults it.
4. `pytest test/krrood_test/test_eql/test_verbalization` (baseline 767 passed / 3 skipped)
   and `scripts/format_docstrings.py` on the modified files.

## Done

- Reproduced both manifestations on `main` (no dependency on #196 — see the roadmap section).
- Confirmed by probe that suppressing the aggregate's `referent_id` produces exactly the
  wording the developer asked for on #196's thread, and changes nothing else.
- Branch cut from `main`, draft PR #264 opened and labelled `bug`, manifest and roadmap
  written.

## Next

- Steps 1–4 above.
- Republish the dashboard (`/plan-dashboard eql-verbalization`) after each manifest change.

## Watch out

- `test_set_of_ranking.py` is also touched by unlanded #196; both append a section at the
  tail, so whoever lands second resolves a trivial conflict. The two tests added here rank
  by the *first* selected aggregate so their expected text is stable across #196 landing.
- `plan_item_bootstrap.py open` is broken on `main` (four-space indent into a two-space
  manifest — PR #160's bug, closed unmerged). The manifest entry here was written by hand;
  do not trust `open`/`record` on this plan until that is fixed.
- Local test environment: `python3.12 -m venv` with `random_events`, `probabilistic_model`,
  `krrood` installed, `objgraph`, and pytest run with
  `--confcutdir=test/krrood_test` to skip the root `conftest.py`'s sdt imports.

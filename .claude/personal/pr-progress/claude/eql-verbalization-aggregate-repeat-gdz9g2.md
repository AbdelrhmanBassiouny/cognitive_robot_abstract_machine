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
- Commits `62853d466` (the fix) and `ce290914c` (review round 1) pushed, with `main` merged in
  at `4a5541d2c`; draft PR #264 open, labelled `bug`, description matching the work.
- Manifest, roadmap and dashboard all current.

## Review round 1 (2026-09-05) — three threads, two done, one open

- **r3941169916 / r3941170391 (done, resolved).** *"Money should be a Role for float so we
  would not need to access an extra attribute called `amount`."* Applied in `ce290914c`:
  `Money` is `@dataclass(eq=False) class Money(Role[float])` with no fields of its own, so
  the chains read `statement.income` / `statement.expenses`.
  Consequence flagged on the thread: the rendering follows the shorter chain, so every
  expectation in the module moved from *"the sum of the amount of its income"* to *"the sum
  of incomes of Statements"* — a plural generic instead of a possessive. That is pre-existing
  behaviour (a plain `income: float` field reproduces it on `main`), about one navigation
  instead of two rather than about `Role`. Re-checked by reverting the production change on
  the new domain: the two ambiguity tests still fail without it, so the tests stay
  load-bearing.
- **r3941192834 (open, deliberately).** *"For each statement …"* instead of *"For each
  month"*, on the premise that grouping by a month reached through a statement is the same as
  grouping by the statement. **Verified false**, with data: evaluated over three statements,
  two of them in March, the query returns two rows and March's income sum is `30.0` — the two
  March statements are summed together, so a row is not a statement. The cardinality argument
  runs the wrong way: one period per statement makes the month a function *of* the statement,
  while naming the frame after the statement needs the month to determine the statement.
  Replied with that evidence and three general options (keep the key; name the key with its
  path, *"For each month of a Statement's period"*; name the entity only once the model can
  declare a key identifying), recommending the first plus the third when declarable. Left
  unresolved — it asks to discuss, and it is answered differently from what it asked.

## Next

- Developer answer on r3941192834, and on the two questions asked back there: which test his
  sentence meant (it matches the ranked one, not the ordered one it sits on), and whether the
  possessive-vs-plural-generic wording for a directly aggregated attribute is a third item.
- CI for `4a5541d2c` was still running when this was written; nothing had failed. No check-in
  is armed (personal notes forbid scheduled checks).

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
- **The grouping frame is a different rule.** `_for_each_header` / `_group_label` in
  `query/assembler.py` decide *"For each month"*; this PR's mechanism is `AggregatorRule.build`
  plus `ReferringExpressions`. Keeping the frame question out of this branch is why r3941192834
  is answered rather than implemented.

## Watch out

- `plan_item_bootstrap.py open` is broken on `main` (four-space indent into a two-space
  manifest — PR #160's bug, closed unmerged). The manifest entry here was written by hand;
  do not trust `open`/`record` on this plan until that is fixed.
- Local test environment: `python3.12 -m venv` with `random_events`, `probabilistic_model`,
  `krrood` installed editable, plus `objgraph` and `docformatter`; run pytest with
  `--confcutdir=test/krrood_test` to skip the root `conftest.py`'s sdt imports. `test_typing`
  needs `mypy`, which is not installed there.

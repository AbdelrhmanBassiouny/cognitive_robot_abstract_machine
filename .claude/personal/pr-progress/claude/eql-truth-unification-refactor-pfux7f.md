# PR #99 — eql-truth-unification (rdr-refactor, Track T, Wave 1)

Branch `claude/eql-truth-unification-refactor-pfux7f`, off `main`, draft.
Kicked off via `/plan-item-kickoff rdr-refactor eql-truth-unification`.
Design doc: `krrood/doc/eql/developer/operation_result_truth_unification.md`
(was only on `rdr/oo-plan`; landed with this PR, rewritten to match reality).

## Done

- Characterization tests first: `test_eql/test_core/test_operation_result_truth.py`
  (19 tests, one section per operator family) + a short-circuited-*operator*
  exclusion test in `test_explanation.py`. Three of the truth tests were genuinely
  red beforehand — `is_true` read the raw flag, so a comparator whose comparison
  failed still reported true.
- Dropped the `OperationResult.is_false` field; `is_false` is a property reading
  `bindings[operand._id_]` **raw** (not via `value`/`_process_result_`, which
  answers a different question for a truth-binding operand). `is_condition_false`
  removed.
- All truth writes go through one new helper,
  `SymbolicExpression._build_operation_result_with_truth_`, which copies bindings
  before writing (the operators previously passed `left_value.bindings` by
  reference — an in-place write leaks truth across sibling branches).
- New `TruthValuedExpression`; `_evaluate_child_as_condition_` reduced to a
  pass-through but **kept**; `SatisfiedConditionTracker` simplified to one uniform
  bindings lookup.
- Verified: `test_eql` 1122 passed/4 skipped vs a captured 1102/4 baseline; whole
  `test/krrood_test` 2000 passed/2 failed, both `test_object_diagram.py`, confirmed
  failing identically on stashed `main` (no graphviz `dot` here).
- PR #99 opened (draft), subscribed; plan.yaml updated (`in_progress`, real branch,
  PR number); divergences flagged on tracking issue #94.

## The design fork (read this before touching the invariant again)

The doc's "truth is always read from `bindings[self._id_]`" cannot hold verbatim:
an expression has exactly one binding, and for `Entity`/aggregators/arithmetic
that binding is the **selected value**. Applied literally it made `entity(x)` drop
results where `x` was `0`/empty, and `condition.evaluate()` return `True` instead
of bindings. Hence `TruthValuedExpression` (binding *is* a truth: logical
operators, quantifiers, rule-tree selectors, unions) vs value-producing
expressions, and `_records_truth_` gating the root-level truth filter in
`evaluate()`. `Query` is deliberately value-producing — its `Where` already
filters internally. Also rejected the doc's `_is_false_flag` transition: it keeps
a bool in the second positional slot, so a missed call site compiles with wrong
semantics.

## Next

- Drive CI to green (18 checks; was still running at hand-off).
- Expect conflicts with #89/#90/#92 (same two functions) and a restack through the
  Wave-0 stack, which still contests `base_expressions.py`.
- Answer review comments; keep the PR in draft after each push.

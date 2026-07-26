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

## Commit 2 (43971581) — truth reading moved onto the expression

Found while investigating the coraplex CI failure at 465dd92c. Commit 1 derived every
result's truth from the operand's binding uniformly, so a query selecting `0`, `False`
or an empty collection reported itself unsatisfied — a query's binding is its
*selection*, not a truth claim. `evaluate()` hid it (a query isn't a truth-recording
root, so it's never filtered by truth); only a consumer reading a query result's truth
saw it. Proved by probing an `origin/main` worktree: main gives `(True, [0]), (True,
[1])` for `entity(variable_from([0, 1]))`, commit 1 gave `(False, [0])`.

Fix: `SymbolicExpression._result_is_false_(result)` — the expression answers, not the
result. Default is the binding-truthiness rule (what a bare-condition variable needs,
and what an operator's boolean binding already means); `Query` overrides to never false.
Two red tests first, both green after. Full suite 2002 passed / 2 failed (the same two
pre-existing graphviz `test_object_diagram.py` failures).

**Not established**: that this fix explains the coraplex `test_merge_motions` failure.
Nothing in `coraplex/src` or `semantic_digital_twin/src` reads `is_true`/`is_false`
directly, and the failure shape (paused/interrupted motion states, threading, 28-min
simulated run) is equally consistent with a flake. The re-run on 43971581 decides it —
do not claim the fix resolved it without that evidence.

## Commit 3 (7280394b) — truth bindings kept out of a result's unification

`test_merge_motions` failed **identically on both 465dd92c and 43971581** — same test,
same motion list — so it is reproducible, not the flake the first round assumed. Traced
the real path this time: coraplex's `pre_condition` monitor
(`plans/condition_nodes.py::condition_monitor`) calls krrood's `evaluate_condition`,
which is `any(condition.evaluate())`. (`paused#N`/`interrupted#N` in the failure list are
plain per-tick status monitors that never reach DONE, so they appear in any such list —
`pre_condition#6` is the only EQL one.)

Comparing `evaluate_condition` against an `origin/main` worktree over ten condition
shapes found one divergence: a satisfied `exists(...)` gave False on main, True on the
branch. Cause: operators now bind their truth, and `_process_result_`'s `UnificationDict`
included those truth bindings as if they were selected values (`{…, AND: True}`). For a
quantifier, whose result bindings are otherwise empty, that flipped an empty/falsy
mapping to non-empty/truthy — exactly what `any()` reads. `_unification_of_` now excludes
bindings of truth-valued expressions. Parity with main restored on all ten shapes.

**Deliberately preserved main's `exists`-as-condition answer (False) even though True
looks more correct** — silently improving semantics under downstream packages inside a
refactor is what caused this. Flagged in the commit message as a separate pre-existing
bug worth its own change.

Full suite after: 2004 passed / 2 failed (same pre-existing graphviz failures).

**Still unproven**: that this fixes coraplex. Can't run coraplex locally (needs
mujoco/giskardpy/ROS). The CI re-run on 7280394b is the evidence — if `test_merge_motions`
fails a third time the diagnosis is still incomplete; keep tracing, do not call it fixed.

## Next

- Watch CI on 7280394b, especially `test_each_lib (coraplex)`.
- Expect conflicts with #89/#90/#92 (same two functions) and a restack through the
  Wave-0 stack, which still contests `base_expressions.py`.
- Answer review comments; keep the PR in draft after each push.

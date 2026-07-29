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

## Commits 4 and 5 — the actual coraplex cause (CI GREEN on 6ddb9b4a)

- **4b2d75cd** restored the fresh-result emission in `_evaluate_child_as_condition_` (the
  observers fill `evaluated_expression_ids`/`satisfied_condition_ids` only where unset, so
  a passed-through child result carried a nested evaluation's record outward). Correct
  in itself; did NOT fix coraplex — it failed a 4th time.
- **6ddb9b4a** is the real fix, and it is a COST bug, not semantics. `Predicate.__bool__`
  calls `__call__()`; `IsObjectReachableBy` (the ReachAction pre-condition in
  `test_merge_motions`) deepcopies the world and runs a full reachability simulation.
  Truth used to be a stored field derived once; making it a property re-derived from the
  binding meant every read re-ran the predicate. Measured with a counting value: main
  reads it 1x per bare condition, the branch read it 4x — four simulations inside a
  ThreadedPredicateMonitor racing the executor's bounded tick budget, so the monitor
  never resolved. Fix: memoize truth per OperationResult, and check `_records_truth_`
  before asking a root for truth.

**Lesson for the rest of this programme**: krrood's own suite cannot catch this class —
it uses cheap comparators. A refactor that changes *when* or *how often* truth is derived
is a behavioural change for downstream packages whose bound values have expensive
`__bool__`. Benchmarking with comparators proves nothing; count reads with a
`__bool__`-counting stand-in instead.

Residual (accepted, coraplex green with it): a bare condition reads truth 2x vs main's
1x — the conditions-root check in `_evaluate_conclusions_and_update_bindings_` that the
satisfied-conditions observer requires. Bounded, no longer multiplies.

## Commit 6 (d50cf1d8) — the "accepted" residual was not acceptable

The user merged main (934c8ce4), bringing PR #477 *end-motion-slowdown* + velocity-
convergence changes. Coraplex failed AGAIN, new signature including `MoveTCP#0` (a motion
task, not just monitors). Branch alone was green at 6ddb9b4a; main alone green on coraplex
at b0268aaa; only the combination failed.

Cause: the residual I had documented as "accepted, bounded" — truth read 2x vs main's 1x.
#477 tightened exactly that timing margin. **Lesson: a known cost regression left in place
because it is "bounded" is still a regression; downstream timing budgets are not ours to
spend.** Closed to exact parity, no semantic change:
- tracker checks its structural guard before reading truth;
- `_evaluate_conclusions_and_update_bindings_` reads truth only when conclusions exist;
- `OperationResult._as_fresh_observation_` carries the read truth across the condition
  re-emission (same operand + bindings, so re-deriving was waste).

Verified vs an origin/main worktree: 1/1/2 reads on both (was 1/1/3, originally 4/1/…).

## Review round 1 (e85b6c03) — 9 comments, all answered and resolved

Rename-and-delete only, no behavioural change. Full suite before push: 2014 passed / 2
failed (the two constant graphviz `test_object_diagram.py` failures).

- **Abbreviations in `logical_quantifiers.py`** (3 comments: `val`, `var_val`,
  `cond_val`) — swept both quantifier functions rather than the three flagged lines:
  `val`/`var_val`→`variable_result`, `cond_val`/`condition_val`→`condition_result`,
  `sol`→`solution`, `condition_val_bindings`→`condition_bindings`.
- **"Is `TruthValuedExpression` redundant?"** — answered with a cross-cut table produced
  by actually enumerating the classes; it is not co-extensive with `TruthValueOperator`
  in either direction.
- **"Wouldn't a mixin be better than the `_records_truth_` flag?"** — agreed; the flag
  said the same thing the type already says, so it is gone. `evaluate()` now checks
  `isinstance(self, TruthValuedExpression)` directly.
- **"Should `_result_is_false_` live on `OperationResult`?"** — explained it is already
  the split arrangement asked for: the result caches, the expression decides.
- **"Should `Query._result_is_false_` raise instead?"** — no; instrumented it and found
  `where(subquery)` legitimately asks it twice per evaluation.
- **Test asserted on class names, not types** — agreed, changed to `isinstance` against
  imported `AND`/`OR`.
- **"Remove the design doc"** — removed; nothing referenced it. Its two divergences are
  now recorded in the PR description instead, and noted in the reply so they aren't lost
  with the file.

## Review round 2 (13241772) — a real bug, found by a review question

"Why is a Union a TruthValuedExpression? and where is it used?" — investigating it found
a regression this PR had introduced and shipped.

`Concatenation` inherits `Union`, which commit 1 made a `TruthValuedExpression`. But
`Concatenation` overrides `_evaluate__` to bind the **value** its child selected, not
that child's truth. Both things the marker controls then misfired:

    list(concatenation(variable_from([0, 1]), variable_from([2])).evaluate())
    main:   [0, 1, 2]
    branch: [{Variable(int, ...): 1}, {Variable(int, ...): 2}]

The falsy `0` filtered out by the root truth filter, and the values replaced by the
underlying variable bindings because the concatenation's own binding was excluded from
`_unification_of_`. The existing `test_concatenate` hid it by wrapping the concatenation
in `entity(...)`, where the query is the root and the concatenation's truth is never the
filter. **Lesson: every test for this PR's new marker went through a query root; the
bare-expression shape was the untested one.**

Fix: split the child-chaining out of `Union` into `EvaluatesChildrenInSequence`. `Union`
(and `Next`) keeps the marker because it genuinely binds a truth; `Concatenation` builds
on the base without it. Red-first test on the bare concatenation. Output matches main
exactly again for both shapes.

Also this round:
- `_get_satisfied_expressions` (test-local) moved onto `SymbolicExpression` as
  `_expressions_with_ids_`, per review — which also collapsed a duplicate, since the
  pre-existing `_get_satisfied_names` did the same walk and now maps `_name_` over it.
- Two PDFs (`drawer_explanation.pdf`, `query_graph.pdf`) had been swept into `e85b6c03`
  by a careless `git add` — they are render artifacts the explanation tests write to the
  repo root. Restored to main's bytes. **They are already in `.gitignore` (lines 152,
  154) yet tracked, so the ignore rule never applies** — any test run re-dirties them.
  Offered an untracking follow-up PR; not done here (out of scope). Watch for this on
  every future commit from this repo: check `git status` before `git add`.

All 4 threads reply-and-resolved. Full suite: 2015 passed / 2 pre-existing graphviz
failures.

## Review round 3 (c9724caf) — docstrings, and one rename rejected on evidence

- **"Rename `_expressions_with_ids_` to `_descendent_expressions_with_ids_`, it only
  looks at descendants"** — the premise was wrong: the walk is
  `chain([self], self._descendants_)`, and `self` is load-bearing. Proved it by deleting
  `self` from the chain: 5 satisfied-condition tests fail, because the caller passes
  `_conditions_root_` and in `where(or_(...))` the `OR` *is* the root. Renamed to
  `_subtree_expressions_with_ids_` instead and showed the failing list in the reply.
  **Check a rename request's premise before applying it.**
- **"What does it mean to bind the truth of every child, and why?"** — docstring stated
  the what, not the why. Rewritten: a result it yields is its own, and truth is read from
  `bindings[operand._id_]`, so not recording anything under its own id would make every
  passed-on result silently false.
- **"Why is Union a TruthValuedExpression?" (asked twice)** — answered, and stated it on
  the class. Also raised, unprompted, that after the split `Union` is an *empty* class
  (marker + `EvaluatesChildrenInSequence`), with `Next` as its only production subclass
  and no direct instantiation outside one test — recommended deleting it and folding the
  marker into `Next`. **Thread deliberately left open** awaiting their answer.

Full suite: 2015 passed / 2 pre-existing graphviz failures.

## Review round 4 (fa5e3457) — Union kept, display name fixed

Developer answered the open `Union` question: **option (1), keep it** — no code change,
`c9724caf`'s class docstring already covers it. They also spotted that `query_graph.py`
rendered `Concatenation` under the display name `"Union"`. Removed the override rather
than replacing it: `name` already defaults to `expression.__class__.__name__`, so
deleting the line yields `"Concatenation"` with no redundant assignment; the colour entry
stays. Verified directly via `ColorLegend.from_expression`. The label was already the odd
one out — `Union`'s own subclass `Next` renders under `ConclusionSelector`, so nothing in
the graph was ever labelled "Union" except the one class that is not a union. Thread
resolved. Full suite: 2015 passed / 2 pre-existing graphviz failures.

## f8a8fe56 — first fully green run, 20/20

The user merged main in (`52f4f745`, bringing PR #475 eql-verbalization-p3) and marked
the PR **ready for review** at 16:43Z. Do not convert it back to draft unless *I* push.

Run 30474103931/30474103937: **all 20 checks green** — coraplex (26 min) *and*
semantic_digital_twin, so even the `test_world_sim_state_sync` flake passed this round.
This is the first completed CI run covering the concatenation fix (commit 8); the four
review rounds before it each landed faster than CI could finish, so every intermediate
run (e85b6c03, 13241772, c9724caf, fa5e3457) was superseded mid-flight, and the last
complete run before this was 16ad47d3, which predates the fix.

Verified the user's main-merge locally before trusting it: 2044 passed / 2 failed (the
constant graphviz pair). Count rose from 2015 because main brought 29 new verbalization
tests. No semantic conflict with the `Union` split or the `_subtree_expressions_with_ids_`
rename. mergeable_state now `clean`. Description refreshed to name this head and result.

## Next

- **ef7bb044: coraplex GREEN, 18/19 checks green.** Only red is
  `test_world_sim_state_sync` (sdt), the physics flake that also fails on plain main.
  CI on e85b6c03 queued at time of writing — watch it, though the round touched no logic.
- PR is draft with 7 commits; consider squashing the follow-up fixes into the refactor
  before asking for review.
- Two follow-ups deserving their own PRs: `evaluate_condition` on a satisfied bare
  `exists(...)` returns False on main too (real bug, deliberately preserved here); and
  the sdt `test_world_sim_state_sync` flake is worth a look by whoever owns multi-sim.
- Expect conflicts with #89/#90/#92 (same two functions) and a restack through the
  Wave-0 stack, which still contests `base_expressions.py`.
- Answer review comments; keep the PR in draft after each push.

# PR #192 - match-underscore-rename-and-forwarding + factories-unwrap-match-and-migrate
# (plan match-query-ergonomics)

Draft PR #192, based on `main` - #182 merged on 2026-08-24 and the 2026-08-30
maintenance pass reparented this PR (roadmap section 23). Roadmap sections 17 and 26 have
the full record and the reasoning.

## Done

1. [x] Reparented: branch rebuilt from #182's head with the item's commit `147d098d2`
       cherry-picked (`e6cbfa5d`; one conflict in `core/mapped_variable.py`'s `__dir__`,
       resolved to the extracted `attribute_names_for_completion`). The recorded blocker
       is discharged by the stacking, and pinned by a test.
2. [x] `HasSymbolicAttributes` (`core/mapped_variable.py`) and `HasQueryModifiers`
       (`query/query_modifiers.py`), `f9501c70`. A match forwards attribute access to the
       lowered query's attribute *construction*, so no `Query` member shadows a matched
       class's field, and implements all six modifiers, returning itself.
3. [x] `variable` and `matches_with_variables` back as compatibility properties, as
       roadmap section 4 decided, for the in-flight D-core stack.
4. [x] Tests: blocker repro, `limit`/`ordered_by`, every modifier returns the match, the
       shadowing case, both `isinstance` relationships, the section-6 guard, the
       compatibility properties, and `ordered_by`/`limit` in the mypy fixture.
5. [x] Manifest, roadmap, PR description, dashboard.
6. [x] Review round 2026-08-23 (roadmap section 18), `61b8cb28`: the forwarding covered
       attribute access alone. Every symbolic operation now lives once in
       `CanBehaveLikeAValue`, built on the one expression an implementation reports as
       `_symbolic_expression_`. The developer's parentheses rule (first call is the
       pattern, later calls call the instance) with a callability check, so nothing
       existing changes. Closed two gaps it depended on: a bare query used as a value in
       its own condition was uncorrelated, and `Call` read the return hint off the called
       type rather than its `__call__`. `krrood/doc/eql/user/match.md` documents the rule.
       Suite: 2087 passed, 6 skipped.

7. [x] Naming round 2026-08-23 (roadmap section 19), `da8b5fca`: `CanBehaveLikeAValue`
       renamed `HasSymbolicOperations` (what can be written) against
       `CanBehaveLikeAVariable` (what it is written on, holding the cache). The cache
       cannot move up - it builds mappings whose child must be a `SymbolicExpression`.
       Same round: a match used as someone else's operand was read as a `Literal`, so
       `variable == match` passed every row; `SymbolicExpression._as_operand_` states the
       rule once. Suite: 2088 passed, 6 skipped.

8. [x] Merged `main`, 2026-09-01 (roadmap section 26), `ff5414e0a`. The branch was cut
       from #182's head *before* #182 merged `main` to take #186's `Index` split, so it
       carried none of that hierarchy while rewriting the same `mapped_variable.py` -
       which is the whole of what six identical maintenance comments since 2026-08-28
       were reporting. All three conflicts took both sides: the operators keep this PR's
       routing through `_symbolic_expression_` and gain #186's `Attribute`/`Index`/`Call`
       return types and the `IndexByValue`/`IndexByExpression` split; `has_cause_attributes`
       and `causes()` arrive from `main`'s `do()` operator reading
       `_matches_with_variables_`; `AttributeMatch.assigned_variable` keeps `main`'s
       fresh-copy branch for a shared `Cause`/`Confounder`; `_update_kwargs_from` takes
       `main`'s `IndexByValue` distinction; `test_match.py` keeps both sides' tests. The
       mypy fixture's `a(Robot).battery` pin moved from `CanBehaveLikeAVariable[Robot]` to
       `Attribute[Robot]`, the narrower type `main` landed - roadmap sections 15/16 settle
       "return types name what they build" as this plan's own convention, so reverting it
       would have undone a landed improvement. `test_eql` 1287 passed, 3 skipped; full
       `test/krrood_test` 2269 passed, 5 skipped.

9. [x] Merged `main` again, 2026-09-02 (roadmap section 27), `9482a62c`. `main` took
       cram2#575 (probabilistic queries) the day before, whose `HasExpression` mixin adds
       a base to the same `class Match(...)` statement this PR rewrites - the only
       conflict in the 1,518 lines it brought. Both sides kept: `HasSymbolicOperations`
       and `HasQueryModifiers` say what can be written *on* a match, `HasExpression` says
       what a match *resolves to* for a caller that only wants the expression to scan or
       build, and `Match` owes both answers. Nothing else needed adjusting - #575's new
       code reads a match only through `expression`, the compatibility property this PR
       keeps, so section 6's silent-miss hazard had nothing to catch. `test_eql` 1310
       passed, 3 skipped; full `test/krrood_test` 1916 passed, 5 skipped.

10. [x] Review round 2026-09-03 (roadmap section 28), `f70c1aff4` and `6df7b7516`. The
       developer's first real review of #192 - six threads left minutes after section 27's
       own report, which is why 26 and 27 both recorded "no review threads". Five acted on
       and resolved, one (`_is_own_name_`) a question answered and left open. Asked how far
       the first went, the developer took all three compatibility properties, which is what
       consumed item 3: removing the public `expression` forces the factory unwrapping,
       since `the(match.expression)` was the only spelling for quantifying or selecting a
       match. `_as_operand_` is now applied at all four boundaries that read a value
       standing for an expression. `marginalize_for` re-roots onto the selection. The five
       user docs, the `causes_effect` strings and the `marginalize_for` prose are migrated,
       and `update_fields` / `create_or_update_variable` / `has_cause_attributes` are behind
       the convention. Suite: 1919 passed, 5 skipped.

## Outstanding

- The PR is a draft, as always; the developer marks it ready.
- **One review thread deliberately open**: `match.py:383`, "why do we need
  `_is_own_name_`?". Answered with the measurement - deleting the override turns
  `_chain_expression_`, `_missing_` and `_operands_` into symbolic `Attribute`s instead of
  raising, which is section 6's silent miss and the shape behind #196 and #248 - and left
  for the developer, since the ask was for a reason rather than a change.
- **A cost accepted on the developer's instruction, not discovered later**: #159
  (`D-core-single-class`, open and out of draft) still reads `match.matches_with_variables`
  at `test_underspecified_match.py:60,67` and `match.variable` at line 80, so its cascade
  breaks. Roadmap sections 4 and 17 kept the properties for exactly that; the review
  reversed it. Recorded on the thread, in the PR description and in the roadmap.
- Open for the developer, on #192 and on #181: `HasExpression._get_expression_` and
  `HasSymbolicOperations._symbolic_expression_` return the same object on every class that
  has both, with different declared contracts. Removing the public `expression` settles
  half of it by taking the third name out from under them; unifying the two would change an
  interface `main` landed on 2026-09-01, which is above the bar auto mode decides alone.
- Also for the developer: `AttributeMatch._symbolic_expression_` has no reader anywhere and
  exists only as the hierarchy's abstract member.
- Box-drawing dividers survive in `test_determiner_phase.py`, `test_source_links.py` and a
  few other verbalization test files this branch does not touch; offered as its own pass.
- CI is running on `6df7b7516`. The run on `9482a62c` was all 23 checks green, but that was
  before this round.
- Still refused by design, reported on the PR: a match given to a predicate, which is wave
  1's territory - a query argument there is evaluated uncorrelated even with no match
  involved.
- Item 3 (`factories-unwrap-match-and-migrate`) is folded into this PR and marked `done` in
  the manifest; nothing of it stands alone once this lands.

## Environment

A narrower set is enough when the workspace-root `test/conftest.py` is skipped: a
python3.12 venv with editable `random_events probabilistic_model krrood` plus `mypy`, run
as `pytest test/krrood_test --confcutdir=test/krrood_test`, covers the whole krrood suite
including the typing fixture. `test_rustworkx_utils` and `test_symbolic_math` still need
`flask` and `casadi`, and `test_object_diagram` still needs the Graphviz `dot` binary.
The fuller set below is what the root `conftest.py` itself needs.

No project dependencies in this container. Scratch venv (python3.12 - 3.11 is too old) at
`$SCRATCHPAD/venv`, plus `objgraph mypy black docformatter` and editable `krrood
random_events probabilistic_model giskardpy physics_simulators semantic_digital_twin`.
`semantic_digital_twin` must be in the *same* `pip install` as `giskardpy` and
`physics_simulators`, since it declares them as requirements and pip cannot resolve them
from an index. With that full set the repo-root `test/conftest.py` imports cleanly and no
`--confcutdir` is needed. `test_rustworkx_utils` needs `flask`/`dash` and
`test_object_diagram` needs the Graphviz `dot` binary; both fail on this container
regardless of the diff. Running the suite rewrites
`test_eql/test_verbalization/verbalization_results.py` with different import order - check
it out again before committing.

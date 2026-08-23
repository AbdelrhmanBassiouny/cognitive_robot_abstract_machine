# PR #192 - match-underscore-rename-and-forwarding (plan match-query-ergonomics)

Draft PR #192, based on `claude/match-query-ergonomics-where-rooted-b876wm` (#182).
Roadmap section 17 has the full record and the reasoning.

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

## Outstanding

- The PR is a draft, as always; the developer marks it ready.
- Reported on #181, not fixed here: `verbalization/grammar/query/assembler.py:285` reads
  `expression._chain_expression_` on an `Aggregator`, which has no such attribute, so
  every `Sum` gets the same structural signature and `_is_order_key` treats any two
  aggregates of one kind as the same column. Pre-existing; the developer routes it.
- CI on #192 has not been read since the second push.
- Still refused by design, reported on the PR: a match given to a predicate (a query
  argument there is evaluated uncorrelated even with no match involved - wave 1's
  territory), and selecting a match (`entity(match)`, `the(match)`), which is item 3's.

## Environment

No project dependencies in this container. Scratch venv (python3.12) at
`$SCRATCHPAD/venv`, plus `objgraph plotly matplotlib mypy casadi pyjpt docformatter` and
editable `krrood random_events probabilistic_model semantic_digital_twin`. The repo-root
`test/conftest.py` imports `semantic_digital_twin.robots`, so runs use
`--confcutdir=test/krrood_test`. `test_rustworkx_utils` needs `flask`/`dash` and
`test_object_diagram` needs the Graphviz `dot` binary; both fail on this container
regardless of the diff. Running the suite rewrites
`test_eql/test_verbalization/verbalization_results.py` with different import order - check
it out again before committing.

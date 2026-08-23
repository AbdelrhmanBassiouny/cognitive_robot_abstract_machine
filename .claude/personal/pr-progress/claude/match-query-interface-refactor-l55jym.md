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

## Outstanding

- The PR is a draft, as always; the developer marks it ready.
- Reported on #181, not fixed here: `verbalization/grammar/query/assembler.py:285` reads
  `expression._chain_expression_` on an `Aggregator`, which has no such attribute, so
  every `Sum` gets the same structural signature and `_is_order_key` treats any two
  aggregates of one kind as the same column. Pre-existing; the developer routes it.
- CI on #192 has not been read yet.

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

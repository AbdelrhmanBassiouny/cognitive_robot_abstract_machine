# dag-facade-hardening / rule-tree-context-stack-ownership

Replace `SymbolicExpression._symbolic_expression_stack_` (a class-level mutable
global introduced before #118, whose element type #118 changed) with a
`RuleTreeContextStack` the outermost `with` block creates and owns, held in a
`ContextVar` exactly like `evaluation_context.py`'s `_evaluation_context_var`.
Stacked on #118's branch `claude/dag-facade-hardening-emrhza`. Tracking issue #96.

## Verification of the original idea (developer's question)

Pure instance-ownership is impossible: `add()`, `refinement()`, `alternative()` and
`next_rule()` are reached from freshly-built, unattached nodes (the three selectors
via `classmethod`s with no instance at all), so the only route to an enclosing root
is `_conditions_root_`/`_root_` - the very facade this plan deletes. Ambient lookup
is unavoidable; what the change removes is the *process-global mutable list*.

## Plan

1. Failing-first tests in `test_eql/test_core/test_rule_tree_context_stack.py`. - done
2. `RuleTreeEditWithoutEnclosingBlock` + `UnbalancedRuleTreeBlockExit`. - done
3. New `entity_query_language/rule_tree_context.py`: `RuleTreeContext` (moved),
   `RuleTreeBlock`, `RuleTreeContextStack`, module-private ContextVar. - done
4. Migrate `base_expressions`, `query.py`, `conclusion.py`,
   `conclusion_selector.py`. - done
5. Suites + `format_docstrings.py`, commit, push, plan state. - done

## Done

- Confirmed empirically on the #118 tip that all four DSL entry points raise a raw
  `AttributeError` outside a `with` block, and that `Conclusion.__post_init__`'s
  `_conditions_root_` fallback is dead (a fresh `Add` resolves it to itself).
- `Query.__enter__` deleted entirely: `Query` now only overrides
  `_rule_tree_anchor_`, so the enter/exit asymmetry (a query module pushing onto
  base-class state, with no matching `__exit__`) is gone.
- The three selectors' duplicated stack lookups collapse into one
  `ConclusionSelector._enclosing_condition_`.
- #118's two splice regression tests pass unmodified.

## Next

- PR #142 open as a **draft**, base `claude/dag-facade-hardening-emrhza` (#118's branch),
  head d795e183. No `bug` label. Subscribed to its activity; CI was still running at
  hand-off - watch and drive to green. No promote link: it cannot go upstream until
  #118 lands.
- Ask the developer whether removing `Conclusion.__post_init__`'s dead
  `_conditions_root_` fallback is right, or whether it encoded an intent that never
  worked.
- Suites: 1415 passed, 6 skipped. The 2 `test_object_diagram` failures are a missing
  Graphviz `dot` binary in this container, the same environmental failure #118 recorded.
- Plan bookkeeping done: item + roadmap addendum saved, dashboard republished at
  https://claude.ai/code/artifact/572b350a-c601-4122-8c12-b80700d22514, structural
  record on #96 (comment 5178214735).
- Deliberately out of scope (developer's call): the cross-thread regression test.
  A real defect exists - with two threads in `with` blocks, one thread's blind
  `__exit__` popped the other's frame - and the ContextVar fixes it, but it ships
  uncovered, so no `bug` label on this PR. Recorded in the plan's roadmap.

## Environment notes

Local Python 3.11 is too old; venv at the session scratchpad `venv/` built with
`uv venv --python 3.12`, deps from `krrood/requirements.txt` +
`probabilistic_model` + `random_events` + `casadi` + `mypy` + `docformatter`.
Run pytest with `PYTHONPATH=krrood/src:test:probabilistic_model/src:random_events/src`
and `--confcutdir=test/krrood_test`. The suite regenerates
`verbalization_results.py`, `drawer_explanation.pdf` and `query_graph.pdf` - revert
those before committing.

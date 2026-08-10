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

- PR #142 open as a **draft**, base `main`, head df0aef5e. No `bug` label. Subscribed.
- #118 merged 2026-08-05, so GitHub retargeted #142 onto `main`; `main` merged in
  cleanly (df0aef5e). A stack-maintenance routine had reported a conflict naming no
  files - there was none, because this branch already contained #118's commits. Its
  `needs-resolution` label was cleared, since a labelled branch is skipped by later
  passes and would have stayed parked.
- Post-merge suites: 1443 passed, 6 skipped (2 `test_object_diagram` = missing
  Graphviz `dot`, reproduces on `main`). PR description rewritten for the new base.
- Second false-positive conflict report (2026-08-05, after main moved to 0626bdce):
  merged main again at 41de0a63, clean, pushed. Diagnosis recorded on the PR
  (comment 5197102942): `stack.py:1177` decides conflicts with
  `git merge-tree --write-tree <parent> <ref>`, and that command returns 0/CLEAN on
  the exact refs the pass used, while GitHub reported `mergeable_state: clean`
  throughout - so the conflict comes from the agent-driven integration step, not
  repository state. Both reports left "Conflicting files:" empty. The routine also
  broke its own SKILL.md step 4.4 (clear the label unless `dirty`) and the
  label/report pair deadlocks: leaving the label parks the branch forever, clearing
  it guarantees a repeat report. Needs a fix in the routine, not here.
- 2026-08-10: the stack routine merged main again at 77f79a99 (clean; no conflict
  report this time). Local fast-forwarded to it; diff vs main unchanged at 8 files,
  +424/-102.
- CI red on 77f79a99 across ~8 `test_each_lib` jobs - NOT this branch. `greenlet`
  3.5.5 was published 2026-08-10T13:28:09Z with wheels only for macos/win and no
  sdist, so `uv` cannot install it on Linux; jobs started 13:36 and die at dependency
  resolution before any repo code is imported. greenlet is transitive (SQLAlchemy)
  and pinned nowhere, so every branch is hit: `eql-symbolic-function-sdt` failed 7/8
  jobs with the identical error in the same minute. Diagnosis on the PR (comment
  5241078820). Deliberately NOT pinning greenlet on this branch - the fix belongs on
  main so it covers every branch, and would be unrelated infra in a focused PR.
  Expect it to clear itself (partial upload); if not, main needs a constraint
  excluding 3.5.5. Just re-run this PR's checks once greenlet installs again.
- CI green on df0aef5e (all 20 checks). Local suites after the second merge:
  1443 passed, 6 skipped, 2 graphviz-`dot` failures that reproduce on main.
- Dashboard tooling bug found, NOT fixed here (would bundle unrelated `.claude/`
  cleanup into a focused PR): `build_dashboard.py:1232` gates "Ready to review" on
  every dependency having an *open* PR, so a *merged* dependency drops the dependent
  off the list - the opposite of the docstring's intent. #142 vanished from
  "Ready to review" the moment #118 landed. Worth its own tiny PR on `main`.
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

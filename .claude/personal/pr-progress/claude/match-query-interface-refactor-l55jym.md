# PR #192 - match-underscore-rename-and-forwarding (plan match-query-ergonomics)

Draft PR #192, based on `claude/match-query-ergonomics-where-rooted-b876wm` (#182).
Plan item `match-underscore-rename-and-forwarding`; roadmap section 17 has the full
record and the reasoning.

## Plan

1. [x] Reparent: branch rebuilt from #182's head with the item's commit `147d098d2`
       cherry-picked (one conflict in `core/mapped_variable.py`'s `__dir__`, resolved to
       the extracted `attribute_names_for_completion`). `test_eql` green: 1197 passed.
2. [] `HasSymbolicAttributes` in `core/mapped_variable.py`: the guards, `__dir__` and the
       `_get_symbolic_attribute_` hook shared by `CanBehaveLikeAVariable` and `Match`.
       Closes the hole where every public `Query` member shadows a matched-class field.
3. [ ] `HasQueryModifiers` in `query/query_modifiers.py`: `where`, `having`, `ordered_by`,
       `distinct`, `grouped_by`, `limit` declared once; `Match` forwards the five it lacked
       and returns itself.
4. [ ] Reconcile the section-7 deviation as section 4 decided: `variable` and
       `matches_with_variables` return as public compatibility properties for the in-flight
       D-core stack (#67/#68/#98/#159); item 3 removes them.
5. [ ] Section 6's guard test: the old public names forward to the matched class instead of
       returning match internals.
6. [ ] Test that `match.where(match.<attribute> >= x)` filters - the recorded blocker,
       true only stacked on #182.
7. [ ] Update PR description, republish the dashboard, re-draft the PR after the push.

## Environment

No project dependencies in this container. Scratch venv (python3.12) at
`$SCRATCHPAD/venv`, plus `objgraph plotly matplotlib mypy casadi pyjpt` and editable
`krrood random_events probabilistic_model semantic_digital_twin`. The repo-root
`test/conftest.py` imports `semantic_digital_twin.robots`, so runs use
`--confcutdir=test/krrood_test`.

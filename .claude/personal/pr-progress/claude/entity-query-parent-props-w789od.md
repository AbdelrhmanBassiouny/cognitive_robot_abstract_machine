## PR #90 — is_condition_participant structural-_parent_ bug (entity-query-parent-props-w789od)

Branch `claude/entity-query-parent-props-w789od`, off `main`, PR #90 (draft, `bug`
label, subscribed to all activity, 1h check-in scheduled).

Origin: user asked whether EQL's structural `_parent_`/`_parent__` fields on
`SymbolicExpression` make sense given the expression graph is a documented DAG (nodes can
have multiple parents), and whether a cleanup PR was warranted. Investigated every
`_parent_`/`_parent__` read site (avoiding `_last_parent_of_type_`, which PR #89 — open,
unmerged — removes as dead code). Almost all reads are legitimate construction-time DAG
wiring (setting edges, splicing rule trees in `conclusion_selector.py`) — not ambiguous.
The one genuine evaluation-time misuse: `evaluation.py`'s `is_condition_participant`,
which classifies nodes for `satisfied_condition_ids` (inference explanations) and
`QueryGraph` satisfaction coloring by reading a node's single structural, first-
attachment-wins `_parent_` — wrong when a node is reused across two unrelated queries,
since the pointer keeps referencing whichever parent attached it first, not the query
currently asking.

Per developer direction: proved it via TDD (failing test first) rather than reasoning
abstractly, and the fix must make "parent" an evaluation-context-dependent value, not a
structural one — mirroring the `ActiveConditionsRoot` pattern already in
`evaluation_context.py` for the same reason.

Status: DONE, both commits pushed.
1. [x] `is_condition_participant` (live evaluation path, `SatisfiedConditionTracker`):
   added `TruthValueOperatorChildren` to `EvaluationContext`, recorded at
   `TruthValueOperator._evaluate_child_as_condition_` (the one chokepoint where the
   dynamic, per-pass parent is known with certainty). Falls back to structural `_parent_`
   only outside an active evaluation. Regression test:
   `test_satisfied_conditions_for_bare_condition_shared_with_an_unrelated_query`.
2. [x] `QueryGraph` (`construct_graph`, `_is_faded_gate`): these run post-hoc after
   evaluation finishes, so the EvaluationContext fix doesn't reach them. Gave
   `is_condition_participant` an explicit, sentinel-defaulted `parent` parameter and
   threaded the locally-known parent through both call sites (the traversal already knows
   it — `construct_graph` recurses via `_children_`, `QueryNode.parent` is set right after
   each visit). Regression test:
   `test_query_graph_marks_a_shared_bare_condition_satisfied_from_its_own_query`.

Verified after each commit: full `test_eql` (1037 passed, 4 skipped) + `test_ormatic`
(131 passed) green, zero regressions, in a from-scratch venv built in this sandbox
(no pre-installed project venv here — had to editable-install krrood + random_events +
probabilistic_model and resolve missing deps one at a time; `--confcutdir=test/krrood_test`
needed to dodge the root conftest's semantic_digital_twin/ROS pull-in). Ran
`scripts/format_docstrings.py` (black + docformatter) on every touched file per AGENTS.md.
Commits authored as `Abdelrhman Bassiouny <abassiou@uni-bremen.de>` — confirmed with the
developer via AskUserQuestion, since this session's local git config was wrongly set to
`Claude <noreply@anthropic.com>` and repo history shows multiple candidate identities for
the developer that didn't match the session's on-file email.

Explicitly flagged as a separate, out-of-scope follow-up in the PR description (not
fixed): `QueryGraph.construct_graph` memoizes one `QueryNode` per expression, so a node
reached via two different parents *within the same query's own tree* (not just across
unrelated queries) only has its classification computed from whichever parent visited it
first — would need a deeper look at `QueryNode`'s one-node-per-expression model.

Open design question (asked by developer, not yet answered in-session at last update):
whether this fully eliminates `_parent_`/`_parent__` as structural fields, or whether they
remain load-bearing elsewhere (construction-time wiring) and only the *read-for-
classification* usage was the actual problem.

Next: watch PR #90 CI/reviews (subscribed); no further code work planned unless review
raises something or the developer asks for the intra-query QueryGraph follow-up.

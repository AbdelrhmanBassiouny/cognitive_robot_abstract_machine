## PR #90 — is_condition_participant structural-_parent_ bug (entity-query-parent-props-w789od)

Branch `claude/entity-query-parent-props-w789od`, off `main`, PR #90 (draft, `bug`
label). Not currently event-subscribed: the original session's subscription died with
it, and this session's re-subscribe attempts were denied/failed. No check-ins armed
(the old 1h one fired and self-disabled; scheduled checks are banned per personal
notes anyway).

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

Review round 2026-08-01 (handled same day by a /plan-item-resolve session, commit
58671190 pushed): 8 review threads + a summary asking for in-session discussion.
Actions taken, all verified by full `test_eql` (1143 passed, 3 skipped) and
`test_ormatic` (132 passed) in a fresh py3.12 venv (3.11 breaks on
`make_dataclass(module=...)`), formatted via `format_docstrings.py`:
- Added `EvaluationContext.is_child_of_truth_value_operator(expression)`;
  `is_condition_participant` now uses it instead of reaching into the record. Unit
  test added in `test_core/test_evaluation_context.py`.
- Dropped the redundant `is_condition_participant` check from
  `construct_graph.is_satisfied` (membership in `satisfied_condition_ids` already
  implies participant-hood — the tracker's filter is the set's only producer) and
  reverted `construct_graph`'s `parent` parameter entirely.
- Deleted the `_PARENT_NOT_SUPPLIED` sentinel: with the construct_graph caller gone,
  plain `Optional = None` behaves identically at every call site. The reviewer's
  suggested `UNSET` exists only on the rdr stack (`rdr/utils.py` on `D-core-engine`),
  not on `main`/this branch.
- Renamed `expr`/`expr_id` identifiers to full words; removed the `..note::`.
- Kept the check in `_is_faded_gate` (dropping it would make every non-condition node
  an unsatisfied gate and fade the whole graph) and kept the recording at
  `base_expressions.py:844` (feeds the tracker path — the primary fix).
Replied to all 8 threads with the attribution footer; resolved the 5 with concrete
changes; left the 3 judgment threads (faded-gate necessity, usage audit, recording
necessity) open with justifications for the developer. PR description updated; PR
still draft.

Summary discussion (held in-session 2026-08-01 and accepted by the developer — after a
false start where the commit was pushed before the discussion, and the discussion was
at first wrongly recorded as already held): `is_condition_participant`
stays — needed at its two remaining functional call sites. On "would rustworkx
traversal/queries beat the growing context-record machinery": no — the recurring bugs
are ownership/context bugs ("who is asking"), not traversal bugs; evaluation is lazy
streaming recursion unsuited to a materialized graph; rustworkx is already used where
structural queries fit (QueryGraph). The genuine consolidation is dag-facade-hardening
Wave 1 Phase B (one reusable context accessor — `is_child_of_truth_value_operator` is
its first slice) plus Phase A rename + Phase D guard test. Watch-item recorded: if
per-owning-query caches multiply (Phase C), consider a single ownership collaborator
on EvaluationContext rather than parallel record classes.

Downstream: PR #92 merges this branch in and touches `query_graph.py` — it must
re-merge this branch's tip (58671190); the construct_graph revert may conflict with
its QueryGraph memoization fix. Recorded in the plan manifest.

Next: react to further review events when they arrive (no subscription — re-subscribe
was denied; the developer will prompt). The summary discussion is settled and its
conclusions are recorded in the plan manifest and roadmap addendum (rustworkx declined;
Phase B consolidation confirmed; ownership-collaborator watch-item on Phase C); commit
58671190 stands. No further code work planned unless review raises something or the
developer asks for the intra-query QueryGraph follow-up.

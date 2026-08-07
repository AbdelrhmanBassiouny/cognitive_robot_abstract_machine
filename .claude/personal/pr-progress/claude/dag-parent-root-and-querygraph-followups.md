# PR #92 — `pr-92-shared-node-followups` (plan `dag-facade-hardening`)

## What this PR is now

Fix 1 only: `InferenceExplanation.query_root` resolved from the evaluation's own
`OutermostQueryClaim` instead of walking the structural `_root_` chain.
4 files, +118/-10.

Fix 2 (the `QueryGraph` memoization order-bug) was **dropped** — see below.

## Done (2026-08-07, via `/plan-item-resolve`)

- Diagnosed the stall: not CI (20/20 green), not review (zero review threads).
  `mergeable_state: dirty` + `needs-resolution`, one conflicting file
  (`query_graph.py`), three routine bot comments all naming it.
- Root cause: this branch merged an *earlier* #90; `d63dce6b` (#90 tip) is not an
  ancestor of it but is of `main`. #90's review round then deleted the machinery
  fix 2 was built on. Predicted verbatim in `pr-90`'s own manifest notes.
- Verified empirically on clean `main`: fix-2 test **passes** unmodified (so its
  production change is dead), fix-1 test **fails** with a real assertion (so fix 1
  is still needed).
- Resolved `query_graph.py` to `main` wholesale — the branch no longer touches it.
  Dropped `_is_satisfied`, the `parent` param, the `or`-fold.
- Kept fix 2's test as a visit-order-independence guard; renamed after the
  behaviour, docstring rewritten (it narrated a mechanism that no longer exists).
- Suites: **1437 passed, 7 skipped, 0 failed** (`test_eql`, `test_ormatic`,
  `test_class_diagram`, `test_class_diagrams`, `test_ripple_down_rules`).
- Pushed `c7253f8b`; `needs-resolution` cleared by hand; PR title + body rewritten;
  `plan.yaml` + `roadmap.md` addendum saved.

## Review round 1 (2026-08-07, commit `82859a81`)

Three threads, all from the developer on `c7253f8b`, all replied to and resolved:

- `explanation.py:688` "remove the word claim, rename to `outermost_query`" →
  `OutermostQueryClaim` → `OutermostQuery`, field
  `outermost_query_claim` → `outermost_query`. Renamed the class too, not just
  the attribute; flagged that in the reply.
- `evaluation_context.py:238` "remove the word claimed" → gone from the field
  docstring, `is_nested`'s docstring and the class name. Also collapsed
  `_query_id` into `node` — storing the node made the id field redundant, and
  that redundancy was this PR's own doing.
- `explanation.py:671` "isn't this general for all expressions? move it into
  SymbolicExpression and simplify the docstring" → agreed. `_resolve_query_root`
  is now `SymbolicExpression._evaluating_query_root_` beside `_root_`/
  `_root_query_`; `base_expressions.py` already imported
  `get_evaluation_context`, so no import problem.

Four new tests (three for `OutermostQuery`'s contract, one for the fallback
branch, which nothing covered). Suites: **1441 passed, 7 skipped, 0 failed**.

## Next

- Waiting on CI for `82859a81`.
- PR stays a **draft** until the developer signs off.
- **Blocked on nothing.** `depends_on` (#90) merged 2026-08-03.
- Minor: running `format_docstrings.py` reflowed two pre-existing docstrings in
  `test_evaluation_context_lifecycle.py`. Mandated by AGENTS.md but it is
  unrelated diff noise — revert if the developer objects.

## Watch-outs

- `subscribe_pr_activity` fails for this repo (both the CCR and GitHub MCP variants,
  and for tracking issue #96 too). No event stream — check state manually.
- Handed to Phase D, not fixed here: `_is_faded_gate` reads `node.parent` while
  `_add_children_to_graph` reassigns `child_node.parent` each visit, so a
  two-parent node keeps only the last-assigned one. Recorded on
  `quantified-conditional-and-audit`.
- Env note: repo git identity was `Claude <noreply@anthropic.com>` (AGENTS.md
  forbids it); set repo-locally to `Abdelrhman Bassiouny <abassiou@uni-bremen.de>`.
  Test env needs Python 3.12 + `--confcutdir=test/krrood_test` and
  `PYTHONPATH=krrood/src:probabilistic_model/src`; venv at
  `<scratchpad>/venv312`.

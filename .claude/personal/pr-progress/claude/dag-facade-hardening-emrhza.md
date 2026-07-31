# dag-facade-hardening / insert-at-ownership-parentage — PR #118 (draft, `bug`)

Resolve `ConclusionSelector.insert_at`'s splice parentage from the owning
rule-tree context instead of `anchor._parent_`. Tracking issue: #96.

## Plan

1. Failing-first tests in `test_eql/test_core/test_rules.py`. — done
2. `RuleTreeContext` on the `with`-context stack (`core/base_expressions.py`),
   pushed by `SymbolicExpression.__enter__` and `Query.__enter__`. — done
3. `insert_at` splices above the recorded owning parent, refreshing it after
   the splice; structural parent still the fallback. — done
4. Suites + `format_docstrings.py`. — done
5. Commit, push, draft PR, plan state. — done

## Done

- Reproduced on `main` with core EQL + `rules/` alone (no RDR, no serializer):
  the earlier sibling's `Comparator` ends up with a `Refinement` as left operand.
- Both new tests verified failing before the fix, passing after (stash check).
- `test_eql` + `test_ormatic` + `test_class_diagrams` + `test_ripple_down_rules`:
  1349 passed, 6 skipped. The 2 `test_object_diagram` failures are a missing
  Graphviz `dot` binary in this container and reproduce on unmodified `main`.
- PR #118 opened as draft with the `bug` label; subscribed to its activity.
- `plan.yaml` updated (branch/PR/status/session) + roadmap "How it was fixed"
  section; dashboard republished.

## Next

- CI was still queued/in-progress at hand-off — watch #118's checks and drive
  to green.
- #78 left untouched deliberately. Its "re-point the regression test" option
  is unavailable (that test lives in `test/krrood_test/test_eql_rdr/`, absent
  on `main`), so the real choice is close-as-superseded or leave to its own
  session.

## Environment notes

Local Python 3.11 is too old (`make_dataclass(module=...)` needs 3.12, which CI
uses). Venv at the session scratchpad `venv/`; run pytest with
`PYTHONPATH=krrood/src:test:probabilistic_model/src` and
`--confcutdir=test/krrood_test` (the repo-root `test/conftest.py` pulls in
`semantic_digital_twin`). Running the suite regenerates
`verbalization_results.py`, `drawer_explanation.pdf` and `query_graph.pdf` —
revert those before committing.

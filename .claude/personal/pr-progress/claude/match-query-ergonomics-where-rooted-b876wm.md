# PR #182 — query-rooted attribute in a query's own conditions does not filter

Plan item `match-query-ergonomics` / `where-query-rooted-attribute-no-filter`.
Branch `claude/match-query-ergonomics-where-rooted-b876wm`, off `main`, draft PR
#182, `bug` label. Roadmap §8 carries the reasoning.

## Status: implemented, pushed, awaiting review

Commit `871be277`. Full krrood suite green locally (2100 passed, 5 skipped).

## What landed

- `Query._correlate_conditions_` / `_correlate_condition_` /
  `_is_attribute_of_self_` / `_rerooted_on_selection_`, called from
  `Query.where` and `Query.having`.
- `MappedVariable._reroot_on_` plus `_mapping_arguments_` on `Attribute`,
  `Index`, `Call`, `FlatVariable` (abstract on the base, so a new mapping type
  cannot silently be skipped).
- `AmbiguousQueryAttribute(UsageError)` for a query selecting several variables.
- `test/krrood_test/test_eql/test_core/test_query_rooted_conditions.py`: 6 tests,
  5 of which fail on the unfixed source (verified by stashing the fix); the sixth
  is the regression guard that a chain rooted at *another* query keeps its
  subquery meaning, and passes both before and after by design.

## Recorded

- Issue #181 and issue #137: the cross-check the item notes asked for — #137's
  binding-order work does **not** subsume this fix.
- `plan.yaml` notes carry the outcome; roadmap §8 written; dashboard republished.

## Next / outstanding

- Nothing outstanding on the PR itself. CI has not reported yet at the time of
  writing.
- Downstream consumers (coraplex, semantic_digital_twin, probabilistic_model)
  could not be exercised locally — their deps are unavailable in this container.
  CI covers them.
- Item 2 (`match-underscore-rename-and-forwarding`) stays blocked until this
  lands; once it does, its blocker condition (`q.where(q.battery >= 50)` through
  the forwarding) is satisfied.

## Notes / hazards

- Self-reference is detected by `_id_`, never `is`: attaching a mapped variable
  copies the query node (same `_id_`), and `Query._compile_` replays conditions
  onto a product that also shares the `_id_`.
- The selection path is deliberately untouched:
  `set_of(match.expression.parent, ...)` relies on the chain staying rooted at
  the lowered query so the match's conditions come with it (roadmap §3/§4).
- Environment: krrood is not installed in this container. Tests were run with a
  hand-built python3.12 venv under the scratchpad and
  `PYTHONPATH=krrood/src:probabilistic_model/src:.`, with
  `--confcutdir=test/krrood_test` to skip the workspace-wide root conftest.
  Four modules could not be collected there for unrelated missing deps
  (`test_ripple_down_rules/test_object_diagram.py`, `test_rdr.py`,
  `test_rdr_alchemy.py`, `test_rustworkx_utils/test_mesh_three_graph_visualizer.py`).

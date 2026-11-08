## Plan
- Core is declared once in `[tool.krrood.core-boundary]` of krrood/pyproject.toml: patterns, class_diagrams, symbol_graph, exceptions, utils, singleton, _version. `CoreBoundaryChecker` checks the module-level import graph; a runtime backstop test catches the rest. Source reading lives in `krrood.source_analysis`.

## Done
- 245f68b570 + 0a78cbaaa7: utils + singleton in core; patterns.role_predicates -> entity_query_language.role_predicates (api-break); 5 crossings in 4 files left. Tests (core boundary, source analysis, dev tools, patterns, EQL verbalization) and pre-commit green at 0a78cbaaa7.
- 29d1fd7ff8: source_analysis.property_return_statement / source_extraction moves (api-break); core narrowed.
- #547 merged up to b0421dff7e.
- Source-analysis and core-list threads resolved.

## Next
- Owner to decide: `krrood check --runtime` mode (thread open).
- CI at 0a78cbaaa7 and #547's b0421dff7e not read.
- Labels: suggest new-feature + api-break in place of maintenance.

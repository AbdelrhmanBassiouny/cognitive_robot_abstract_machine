## Plan
- Core is declared once in `[tool.krrood.core-boundary]` of krrood/pyproject.toml: patterns, class_diagrams, symbol_graph, exceptions, utils, singleton, _version. `CoreBoundaryChecker` checks the module-level import graph; a runtime backstop test catches the rest. Source reading lives in `krrood.source_analysis`.

## Done
- 8dcc61cb36: Role.is_same_semantic_entity; EQL's IsSameSemanticEntity calls it. EQL kept out of core (would add 28 crossings). Tests + pre-commit green at 8dcc61cb36; merged into #547 (cb45de5c6d).
- 245f68b570 + 0a78cbaaa7: utils + singleton in core; role_predicates -> EQL; 29d1fd7ff8: source_analysis moves (api-break). 5 crossings in 4 files left.
- Source-analysis and core-list threads resolved.

## Next
- Owner to decide: `krrood check --runtime` mode (thread open).
- CI at 8dcc61cb36 and #547's cb45de5c6d not read.
- Labels: suggest new-feature + api-break in place of maintenance.

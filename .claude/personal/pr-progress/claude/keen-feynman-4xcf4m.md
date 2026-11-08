## Plan
- Core is declared once in `[tool.krrood.core-boundary]` of krrood/pyproject.toml (now the roadmap's krrood-core: patterns, class_diagrams, symbol_graph, exceptions, _version). `CoreBoundaryChecker` checks the module-level import graph; a runtime backstop test catches the rest. Source reading lives in `krrood.source_analysis`.

## Done
- 29d1fd7ff8: code_parsing_utils -> source_analysis.property_return_statement, source_extraction_utils -> source_analysis.source_extraction (api-break); core narrowed, crossings 42 -> 21 in 14 files. main dcfad8668 merged. 164 tests passed, pre-commit clean at 29d1fd7ff8.
- #547 (claude/bold-ramanujan-vb0e9c): merged at d1025bd5b5, rdr import fixed in 8fc5a7dd86.
- Thread on source_analysis resolved.

## Next
- Owner to decide: add krrood.utils + krrood.singleton to core; move patterns/role_predicates.py into EQL; `krrood check --runtime` mode. Threads left open.
- CI at 29d1fd7ff8 and 8fc5a7dd86 not read.
- Labels: suggest new-feature + api-break in place of maintenance.

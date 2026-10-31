## Plan
- `_handle_import_node` / `_handle_import_from_node` skip an import whose top-level package `importlib.util.find_spec` cannot find (absolute imports only)
- Dataset mimic: plain `import` of a missing module under `TYPE_CHECKING`; tests at scope and class-diagram type-hint level

## Done
- Branch, draft PR #545, plan item recorded

## Next
- Confirm with developer: `test_get_scope_from_imports_invalid` asserts the old raising contract and must change
- Write failing tests, implement, format via pre-commit, run krrood test_utils + test_class_diagram

# PR plan: D-deco — @rdr decorator + file store (Wave 0, S2)

Final slice of the rdr-engine split. Base: D-ui (not pushed yet — currently
cut from origin/D-core-engine; rebase onto origin/D-ui before opening the PR).

## Plan

1. Copy from origin/rdr-engine, adapted to the refactored code_generation
   package: rdr/decorator.py, rdr/file_store.py, templates/rdr_empty.py.jinja,
   test_rdr_decorator.py, test_rdr_file_store.py, developer + user
   rdr_decorator.md docs.
2. Full test_eql_rdr + test_eql suites, docformatter, revert ORM artifacts.
3. Rebase onto origin/D-ui once it exists, push, draft PR "D-deco -> D-ui",
   subscribe to PR activity.
4. Verify diff origin/rdr-engine vs D-deco leaves only dropped legacy files;
   close umbrella #38 with pointer to the split chain.

## Done

- Sources adapted and smoke-tested end-to-end (decorate → fit → classify
  override → auto-save → reload; enum return types round-trip too).
  Adaptations vs rdr-engine: function_to_dataclass_source →
  FunctionCaseGenerator().generate; to_variable_name →
  camel_case_to_lower_camel_case; _load_module_from_path →
  load_module_from_path(path, prefix); imports made global; template variable
  var_name → variable_name. Both load invariants preserved
  (case_type.function rewired; rdr.save_path always set).
- Tests copied with import adaptations only; docs copied with
  FunctionCaseGenerator references and the now-fixed non-builtin-annotation
  limitation bullet rewritten (verified empirically).

## Next

- Run full suites on python3.12 venv, commit, then wait/rebase onto D-ui,
  open the draft PR, subscribe, close #38.

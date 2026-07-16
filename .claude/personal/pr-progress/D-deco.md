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

- Verify `git diff origin/rdr-engine D-deco` remainder is only the
  intentionally-dropped legacy files (Qt GUI, tracked_object, predicates,
  types, JSON serialization tests — removed by #53) plus
  refactor-superseded filenames, and close umbrella #38 with a comment
  pointing at the split chain.
- Babysit draft PR #77 (subscribed to activity; hourly self check-ins
  armed) until merged or closed.

## Status

- D-ui appeared; rebased D-deco onto origin/D-ui (96e236e8) and
  force-pushed-with-lease. test_eql_rdr on the rebase: 518 passed,
  2 skipped. Draft PR #77 "D-deco -> D-ui" opened with session link;
  subscribed to its activity.
- Earlier: test_eql 1017 passed, 3 skipped. ORM artifacts reverted.
  docformatter run on the two new source modules; the two test files
  intentionally keep the rdr-engine formatting because docformatter's
  multi-line-summary rewrite changes a fixture docstring that
  test_wrapper_dunder_doc_matches_original asserts on verbatim (sibling
  test files in the suite are not docformatter-clean either).

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

- Babysit draft PR #77 (subscribed to activity; self check-ins armed)
  until merged or closed. At the next check-in: verify CI on the new
  head e53fb418 — expect semantic_digital_twin green (restack removed
  the case_factory= call); watch the coraplex test_merge_motions
  MotionDidNotFinish failure (3/3 on earlier #77 runs, main green,
  stack doesn't touch coraplex — diagnosis posted on #76 and recorded
  in #77's known-failures section). Also re-check whether D-ui moved
  again.

## Restacks so far

- D-ui was force-rewritten to linear history (a7eb3703: splice fix
  cfe32ad0 + case-table 2e8c8496 + interactive a7eb3703). Restacked by
  cherry-picking my two commits onto it → head e53fb418 (slice
  9f1823c1 + sweep e53fb418), force-pushed-with-lease. test_eql_rdr on
  that tip: 538 passed, 2 skipped. #77 description updated (restack
  note + known-failures section: sdt resolved-pending-green, coraplex
  open/owned by lower stack).

## Status

- DONE: PR #77 (D-deco -> D-ui, draft) open with session link and
  subscribed; umbrella #38 closed with the split-chain comment.
- Head 559daaa1 = two commits: the decorator slice (93d2fd05) + the
  final-slice sweep (eql_rdr_refactor_plan.md, rdr_conclusion_domain.py,
  backward-inference docs, test_rule_tree_view.py) so the umbrella diff
  closes. In test_rule_tree_view.py the copy.copy cloning test was
  rewired to _node_for_new_position_ (copy.copy never produced a fresh
  id on rdr-engine either — verified empirically against that branch;
  it only stayed green there behind the zoo-dataset skip guard).
- Rebased twice onto moving bases (D-ui 6b12c1c7, then ccbbe603 after
  the steward restack). On the final base: test_eql_rdr 538 passed,
  2 skipped; test_eql 1058 passed, 3 skipped. ORM artifacts reverted.
- Final umbrella verification: files present only on rdr-engine are
  exactly the #53 legacy drops (gui.py, tracked_object.py,
  predicates.py, types.py, test_json_serialization.py,
  test_predicates.py, test_tracked_object.py, test_qt_gui_inline.py,
  PyQt5-dependent test_ripple_down_rules/test_eql_rdr.py) plus two
  refactor-superseded filenames (code_generation/utils.py,
  test_code_generation_utilities.py) whose content landed via #58/#39.
- docformatter caveat (still true): the two decorator test files keep
  rdr-engine formatting because the multi-line-summary rewrite breaks
  test_wrapper_dunder_doc_matches_original's verbatim docstring
  assertion.

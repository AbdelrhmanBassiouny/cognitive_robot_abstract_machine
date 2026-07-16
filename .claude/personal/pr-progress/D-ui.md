# PR plan: D-ui — interactive expert interface (Wave 0, S1)

Draft PR #76 (`D-ui` -> `D-core-engine`) is OPEN and watched.
Session: https://claude.ai/code/session_01B3Ji1kNxRinif4y1dD2xPy

## Done

- Cut `D-ui` from `origin/D-core-engine`; copied from `origin/rdr-engine`:
  interactive.py, magics.py, case_table.py, prompt_examples.py,
  prompt_sections.py, `__init__.py` exports (minus decorator/file_store —
  those stay for D-deco), all 17 planned tests, fitted_models/, conftest.py
  TTY-skip fixture, and the eql_rdr_conclusion_asking developer + user docs.
- No copied test imports decorator.py or file_store.py — nothing deferred
  to D-deco.
- Reconciled against the split tip: ResolutionMode.SILENT -> AUTOMATIC
  (test_hint_mode), CaseSerializer.to_source returns CaseSource not a tuple
  (test_case_serializer), retired `underspecified()` factory ->
  `an(...).from_(...)` (test_interactive_human_fit).
- Found + fixed a real engine regression the fitted-model test exposed:
  `insert_at` spliced above `anchor._parent_`, which for a shared-identity
  MappedVariable anchor can be an incidental Comparator from an earlier
  sibling branch (saved zoo model authors `refinement(eggs == False)` before
  `refinement(eggs)`); the splice dragged the refinement chain into the
  Comparator, silently dropping 12/21 rules (101/101 -> 71/101). Restored
  structural-parent recovery via reintroduced `_last_parent_of_type_`.
  Failing-first DSL repro: TestAttributeReusedInEarlierSiblingBranch in
  test_rule_tree_growth.py. Isolated as first commit 7cd1f993 so the steward
  can fold it down into #68 if preferred.
- Verified: full test_eql_rdr + test_eql = 1494 passed, 5 skipped; fitted
  zoo model reproduces 101/101; ORM artifacts reverted; docformatter run.

## CI status (head ccbbe603, 2026-07-16)

- Merged the restacked D-core-engine (fa1e46c0) into D-ui; resolved the
  conclusion_selector.py formatting conflict (base commit fab3aeae enforces
  black+docformatter repo-wide); ran scripts/format_docstrings.py over all
  PR-touched files; re-verified 1535 passed, 5 skipped.
- Only failing check: test_each_lib (semantic_digital_twin) —
  CaseQuery.__init__() got an unexpected keyword argument 'case_factory' in
  semantic_digital_twin/reasoning/reasoner.py (legacy ripple_down_rules API
  drift). PRE-EXISTING: the identical job fails on the base D-core-engine
  run at fa1e46c0 (run 29518169104). Not caused by D-ui; belongs to the
  steward's stack (likely #53's legacy-RDR refactor). test_each_lib (krrood)
  is green on the PR head.

## Next

- Handle PR #76 review comments / CI events as they arrive; re-check via
  hourly send_later self check-in until merged/closed.
- Flag to the steward (S0): the engine fix commit 7cd1f993 may belong in
  #68, and the semantic_digital_twin CaseQuery failure is theirs.
- D-deco (S2) bases on D-ui per the roadmap; it can start now that D-ui
  is pushed.

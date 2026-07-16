# PR plan: D-ui — interactive expert interface (Wave 0, S1)

**D-ui is now a 3-PR stack** (split on user request; original monolithic PR
was too big). All draft, all watched. Session:
https://claude.ai/code/session_01B3Ji1kNxRinif4y1dD2xPy

| PR | branch | base | contents |
|---|---|---|---|
| #78 | `D-ui-splice-fix` | `D-core-engine` | insert_at splice fix + regression test (`bug` label) |
| #79 | `D-ui-rendering` | `D-ui-splice-fix` | `case_table.py` + 7 shell-free rendering/serialization tests |
| #76 | `D-ui` | `D-ui-rendering` | interactive.py, magics.py, prompt_sections/examples, conftest, fitted_models, docs, 9 shell tests |

Stack tips (2026-07-16, rebased onto restacked `D-core-engine` 5ccec861):
#78 cfe32ad0, #79 2e8c8496, #76 a7eb3703. Full assembled stack =
1535 passed, 5 skipped; fitted zoo model reloads 101/101.

## Split rationale + dependency facts

- Runtime DAG: case_table + magics are leaves; prompt_examples→case_table;
  prompt_sections→prompt_examples (interactive import is TYPE_CHECKING-only);
  interactive→{case_table,magics,prompt_sections}. So case_table lands in #79
  (a dep of the interactive layer), interactive layer in #76.
- conftest.py imports interactive → the interactive-fixture conftest ships
  with #76; #79 keeps the base conftest (no TTY dep). The 7 shell-free tests
  import only rdr submodules, so #79 is self-contained.
- `test_correct_drawer.py` is a *dataset* (not a pytest module) consumed only
  by shell tests → rides #76 with the drawer fitted model.
- Splice fix based on `D-core-engine`, NOT main: `insert_at` doesn't exist on
  main yet (stack-only), so the "bugfix off main" convention can't apply.
  Flagged to steward it may fold into #68.

## Concurrent-restack handling (IMPORTANT for steward automation)

- While splitting, the steward restacked the WHOLE stack onto latest main
  (D-core-engine fa1e46c0 -> 5ccec861) and pushed a restacked monolithic D-ui
  (af1c4cf1). Confirmed af1c4cf1 touched none of my rdr code — its only delta
  over the new base was my own old monolithic D-ui content.
- Rebased all 3 split branches onto new D-core-engine (clean; my files
  unchanged in the new base) and force-pushed; #76 replaced af1c4cf1 (user
  authorized the force-push over the steward commit).
- New base already carries `638d4782 Restore CaseQuery call compatibility` —
  so the earlier semantic_digital_twin CaseQuery CI failure is resolved
  upstream. No longer ours.
- **Steward automation caveat:** its restack treats D-ui as a monolithic
  direct child of D-core-engine. D-ui is now a child of D-ui-rendering (child
  of D-ui-splice-fix). The automation must learn the two new intermediate
  branches or it will re-restack the wrong parent.

## Original single-PR history (superseded, for reference)

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

- Watch #78, #79, #76 CI/review events until merged/closed; re-check via
  hourly send_later self check-in. Merge order is bottom-up: #78 -> #79 -> #76.
- Known non-actionable CI: `test_each_lib (coraplex)` failed on the steward's
  replaced head 90810979 (test_merge_motions / MotionDidNotFinish) — a
  coraplex motion-planning test from the main cascade, not krrood, likely
  flaky. Re-runs on the new heads; not ours.
- Flag to steward (S0): #78 (splice fix) may fold into #68; the two new
  intermediate branches (D-ui-splice-fix, D-ui-rendering) must be registered
  with the restack automation.
- D-deco (S2) now bases on the new D-ui tip (a7eb3703), not the old one.

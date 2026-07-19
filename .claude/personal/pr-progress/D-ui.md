# PR plan: D-ui — interactive expert interface (Wave 0, S1)

**D-ui is now a 3-PR stack** (split on user request; original monolithic PR
was too big). All draft, all watched. Session:
https://claude.ai/code/session_01B3Ji1kNxRinif4y1dD2xPy

| PR | branch | base | contents |
|---|---|---|---|
| #78 | `D-ui-splice-fix` | `D-core-engine` | insert_at splice fix + regression test (`bug` label) |
| #79 | `D-ui-rendering` | `D-ui-splice-fix` | `case_table.py` + 7 shell-free rendering/serialization tests |
| #76 | `D-ui` | `D-ui-rendering` | interactive.py, magics.py, prompt_sections/examples, conftest, fitted_models, docs, 9 shell tests |

Stack tips: steward's automation has restacked the WHOLE stack THREE times
now. Current heads (3rd restack): base D-core-engine d98d9566; #78 1e4f1fb2;
#79 0a305c68; #76 c50d2109. Each time verified the automation preserved my
commits byte-for-byte: #78 delta over base = exactly my 89-line splice fix
(_last_parent_of_type_ present); #79 = case_table + 7 tests; #76 = interactive
layer + the 2 D-deco handoff files (23 files/7266 ins, incl. rdr_conclusion_domain.py
+ test_rule_tree_view.py). No action needed — automation re-parents all three
correctly; do NOT force-push over it. Locally synced (reset --hard) each time.
Assembled stack last full-verified 1535 passed, 5 skipped; fitted zoo model
reloads 101/101.

`test_each_lib (krrood)` is GREEN on all three current live heads — that's
the only job that exercises my code.

D-deco-session handoff landed on #76 (commit bf5b63c3, on top of restacked
9c7f8e6b): `doc/eql/user/rdr_conclusion_domain.py` (the Exhibit domain my
`eql_rdr_conclusion_asking.md` worked example imports — was dangling) and
`test_rule_tree_view.py` (renderer coverage; imports IPythonInterface so it
must live in #76, not the shell-free #79). Verified: test_rule_tree_view 20
passed, doc import satisfied. Replied on #76 + posted correction that I could
NOT delete `D-deco-rehome-handoff` (git proxy blocks ref deletion). D-deco
session confirmed (2026-07-19) the files landed byte-identical and rebuilt
#80/#77 on the new tip (full test_eql_rdr 538 passed/2 skipped). Loose end:
NEITHER automated session can delete `D-deco-rehome-handoff` (my git proxy
hangs on ref-delete; theirs gets HTTP 403) — harmless staging branch, human
can delete via the GitHub UI. The dangling `eql_rdr_refactor_plan.md` doc is
#68/steward territory, not this stack (already deflected in-thread).

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
- Known non-actionable CI (all EXTERNAL packages, not krrood; systematic
  across the steward's whole cascade, unrelated to my 3 PRs):
  - `test_each_lib (robokudo)`: downloads test data from
    gitlab.informatik.uni-bremen.de -> `[Errno 101] Network is unreachable`.
    CI runner has no egress to that host; each fresh merge-commit misses the
    per-commit test-data cache. Infra fix (network access or seeded cache),
    not code.
  - `test_each_lib (coraplex)`: test_merge_motions / MotionDidNotFinish —
    motion-planning flake from the main cascade.
  - giskardpy / semantic_digital_twin failures seen only on STALE heads;
    green on the current live heads.
- Flag to steward (S0): #78 (splice fix) may still fold into #68. (The
  intermediate-branch coordination concern is RESOLVED — the automation's
  2nd restack correctly re-parented D-ui-splice-fix and D-ui-rendering.)
- D-deco (S2) now bases on the current D-ui tip (9c7f8e6b).

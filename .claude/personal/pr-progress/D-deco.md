# PR plan: D-deco — @rdr decorator (Wave 0, S2b)

Decorator half of the @rdr path, stacked on D-store (#80). Base: `D-store`.
PR: #77 (draft, retargeted from D-ui -> D-store).

## Scope

- `rdr/decorator.py` — rdr() factory + RDRWrapper.
- `rdr/templates/rdr_empty.py.jinja` — empty rule-tree section.
- `test_rdr_decorator.py`, `rdr_decorator.md` (dev + user).

SOLID split preserved; both load invariants hold (case_type.function
rewired; rdr.save_path always set). Adaptations vs rdr-engine:
FunctionCaseGenerator().generate, camel_case_to_lower_camel_case,
load_module_from_path; imports global.

## Split history (2026-07-16)

The original single D-deco PR was too big for review. Root cause: it
bundled two unrelated commits — the real @rdr feature (1993 lines) + an
"umbrella-closure sweep" (1031 lines of orphan files bundled only to make
`git diff rdr-engine <tip>` reach zero for #38).

Resolution:
1. Feature split into #80 D-store (file store) + #77 D-deco (decorator).
2. Sweep dissolved (#38 already closed). Per-file disposition:
   - rdr_conclusion_domain.py -> REHOME #76 (D-ui guide imports it; required).
   - test_rule_tree_view.py -> REHOME #76 (only real renderer coverage; the
     copy.copy assertion was rewired to _node_for_new_position_).
   - eql_rdr_refactor_plan.md -> dangling (un-indexed) design doc; offered
     to steward for #68 or drop.
   - backward_inference_{design,user_guide}.md -> DROPPED (stray krrood/docs/
     path, not in the built doc tree, referenced by nothing).
   Both keepers verified green on D-ui (test_rule_tree_view 20 passed);
   staged for the steward to land (I don't push their branch).

## Stack

main … D-core-engine (#68) -> D-ui (#76) -> D-store (#80) -> D-deco (#77)

## Status

- DONE: D-deco rebuilt on D-store, head 7e89ec60 (single decorator commit),
  force-pushed. #77 retargeted base D-ui -> D-store, description rewritten,
  subscribed. #80 opened + subscribed.
- test_rdr_decorator.py: 20 passed. Full test_eql_rdr on D-deco tip: 518
  passed, 2 skipped (-20 vs before = test_rule_tree_view moved to #76).
- Earlier: on the pre-split tip, full CI was green (all 18 matrix jobs;
  semantic_digital_twin case_factory fixed by restack, coraplex
  test_merge_motions green).
- Steward notified via #76 comment (2026-07-17): register D-store in the
  restack chain, hand off the 2 rehome files (staged on branch
  D-deco-rehome-handoff, cut from D-ui), eql_rdr_refactor_plan.md question.
- 2026-07-19: steward acted. D-ui split further into 3 stacked branches
  (D-ui-splice-fix -> D-ui-rendering -> D-ui) and D-store was registered
  in the restack chain — D-ui/D-store/D-deco all auto-restacked
  (D-ui a7eb3703->9c7f8e6b, D-store 0c4938d3->b7655f11, D-deco
  7e89ec60->86717780). Both my commits preserved verbatim (diffed
  identical old vs new). Re-verified on the new tip: test_rdr_file_store
  21 passed, test_rdr_decorator 20 passed, full test_eql_rdr 518 passed/
  2 skipped.
- Rehome files NOT yet landed on D-ui (still needed) — the old
  D-deco-rehome-handoff branch had gone stale (base drifted through the
  new restack), so I recreated it fresh off the current D-ui tip with the
  same two files, re-verified green (test_rule_tree_view 20 passed), and
  force-pushed. Still just a staging branch, not a PR.
- New CI flake found on #77's current head: semantic_digital_twin ->
  test_multi_sim.py::test_world_sim_state_sync (physics-settling
  assertion). Confirmed unrelated: same job passes on #80, whose only
  diff from #77 is the decorator commit, which never touches
  semantic_digital_twin/physics_simulators. Documented in #77's
  description and flagged on #76; no fix needed here.
- #77 description updated with the restack note + the new flake's
  known-failures entry. Posted update comment on #76.

## Next

- Babysit #80 and #77 until merged/closed (#80 merges first). Watch for
  the steward landing the rehome files onto D-ui (then delete
  D-deco-rehome-handoff) and their eql_rdr_refactor_plan.md decision.

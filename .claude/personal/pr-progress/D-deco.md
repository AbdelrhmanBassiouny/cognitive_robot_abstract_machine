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

## Next

- Notify steward: register D-store in the restack chain; hand off the 2
  rehome files for #76; offer/drop eql_rdr_refactor_plan.md.
- Babysit #80 and #77 until merged/closed (#80 merges first).

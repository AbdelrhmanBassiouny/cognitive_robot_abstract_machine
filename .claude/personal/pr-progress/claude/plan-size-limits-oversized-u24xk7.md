PR #273 (draft) - `refuse-oversized-save` from `plan-size-limits`, based on #207's branch
(`claude/plan-size-limits-budget-alp8p2`) since it needs `SizeBudget` from that unmerged PR.

Done:
- `plan_size_budget.py` gained `PlanOverBudgetError` + `SizeBudget.enforce(size)`.
- New `plan_size_gate.py`, the CLI `save-plan.sh` now calls right after the existing
  `plan_manifest_tools.py read-id` check, refusing a save that would leave a plan over
  budget before anything is written to the scratch worktree.
- TDD throughout; full `.claude/hooks/tests` suite green (217 passed).
- During kickoff, found two more plans over budget that neither existing split covers:
  `knowledge-directed-perception` (29 items, 8,146 lines) and `icra-experiments` (33 items,
  1,833 lines). Added `split-knowledge-directed-perception` and `split-icra-experiments` as
  new plan-size-limits items, and to this item's own `depends_on` alongside
  `size-budget-and-report` (missing from the original list even though the gate imports from
  it). Posted on tracking issue #200.

Next:
- Split `knowledge-directed-perception` and `icra-experiments` (delegating to background
  agents - large, mechanical-but-careful work following the precedent the two prior splits
  already established in the plan's roadmap).
- This PR cannot land (merge) until #207 merges and all four split items are done - it would
  refuse every save of a still-oversized plan otherwise. Fine to keep reviewing/refining as a
  draft in the meantime.

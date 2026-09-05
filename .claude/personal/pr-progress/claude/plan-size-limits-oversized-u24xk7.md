PR #273 - `refuse-oversized-save` from `plan-size-limits`, based on #207's branch
(`claude/plan-size-limits-budget-alp8p2`) since it needs `SizeBudget` from that unmerged PR.

**The user converted #273 to ready-for-review themselves (2026-09-05) - per standing
instructions this means my job on this PR ends here: no further commits, no re-drafting,
no more work on it unless a new session is asked for.**

Done:
- `plan_size_budget.py` gained `PlanOverBudgetError` + `SizeBudget.enforce(size)`.
- New `plan_size_gate.py`, the CLI `save-plan.sh` now calls right after the existing
  `plan_manifest_tools.py read-id` check, refusing a save that would leave a plan over
  budget before anything is written to the scratch worktree.
- TDD throughout; full `.claude/hooks/tests` suite green (217 passed).
- Two review comments (hardcoded `"plan.yaml"`/`"roadmap.md"` instead of `PlanDocument`)
  fixed in 058c7153d, replied to, and resolved.
- During kickoff, found two more plans over budget that neither existing split covers:
  `knowledge-directed-perception` (29 items, 8,146 lines) and `icra-experiments` (33 items,
  1,833 lines). Added `split-knowledge-directed-perception` and `split-icra-experiments` as
  new plan-size-limits items, and to this item's own `depends_on` alongside
  `size-budget-and-report`. Both splits are now done (delegated to two background agents,
  verified): `knowledge-directed-perception` became `knowledge-directed-grounding`/
  `-requests`/`-expectation`; `icra-experiments` became `icra-foundation`/`-mechanism`/
  `-evidence`. All six under budget, `plan-size-limits`'s own manifest updated, tracking
  issue #200 notified for both.
- Republished `plan-size-limits`'s dashboard and the master index (6 new plans, 2 removed).

Outstanding (not mine to act on, since the PR is out of draft):
- Still cannot *merge* until #207 lands - the same `depends_on` reasoning as before, just
  now satisfied on the split side.
- Found two more plans over budget as a side effect of the final report -
  `match-query-ergonomics` (174 lines over) and `montessori-eql-stack` (413 lines over) -
  neither part of what was asked; flagged to the user rather than acted on.

### Next
Nothing outstanding. CI hadn't reported yet as of the last push. Ready for
review — I'll flip it out of draft myself when I've read it.

## plan-size-limits / new-plan-when-full — PR #277
Branch: `claude/plan-size-limits-newplan-ukbbri`, stacked on #207's branch
(`claude/plan-size-limits-budget-alp8p2`) — needs `PlanSize`/`SizeBudget` from
`plan_size_budget.py`, which only exists there. Independent of #273
(`refuse-oversized-save`): only needs `SizeBudget().overruns`, not
`enforce`/`PlanOverBudgetError`.


### Plan
1. `plan_size_check.py` (new, `.claude/hooks/`) — `--manifest`/`--roadmap` in,
   JSON `{item_count, line_count, is_full, overruns}` out, always exits 0.
   Reuses `PlanSize.measure`/`SizeBudget().overruns`.
2. `/add-plan-item` step 5 (new) — measure a covering plan's current size
   before choosing "new item in an existing plan"; full disqualifies it,
   falls through to "new plan".
3. `/plan-create` step 7 (new) — measure the freshly drafted plan before the
   first save; full stops the save and asks whether to split along a seam or
   trim scope, pointing at prior split precedent rather than re-deriving the
   methodology.
4. `resolve-personal-notes-config.sh` gains `PLAN_SIZE_CHECK_SCRIPT`.

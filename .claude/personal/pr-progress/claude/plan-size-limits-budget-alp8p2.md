
# PR #207 - a named size budget, and a report of every plan against it

Wave 1, item `size-budget-and-report` of the `plan-size-limits` plan (tracking
issue #200). Branch `claude/plan-size-limits-budget-alp8p2`, off `main`.

## Plan

1. Name the budget and measure a plan against it, report-only.
2. Give it an entry point a session can actually run.
3. Record the item's state and open the draft PR.

## Done

- `.claude/hooks/plan_size_budget.py`: `PLAN_SIZE_BUDGET` (15 items, 2,000
  combined lines), `PlanSize`, and `SizeBudget.overruns` returning a
  `BudgetOverrun` per blown `BudgetLimit`. Item counts are parsed out of the
  YAML, not matched line by line.
- `.claude/hooks/plan-size-report.sh`: reads the notes branch off `FETCH_HEAD`
  and prints every plan against the budget. Confirmed against the live branch -
  `rdr-refactor` and `workflow-unification` are the two over it.
- 33 tests in `.claude/hooks/tests` (already in CI's `test_claude_dev_tooling`).
  Full hooks suite: 158 passed.
- Blocker resolved: the constants live in a module of their own on `main`,
  not a third copy of `.claude/shared/plan_model.py` (#151/#154). Recorded in
  the plan and its roadmap.
- Draft PR #207 opened; manifest records branch, PR and `in_progress`.

## Next

- Nothing outstanding in this session. Wave 3's `refuse-oversized-save` imports
  `SizeBudget.overruns` from this module for its typed error.
- Rebase hazard: #185 moves every `.claude/` Python module into `bastler/`.
  Whichever of the two lands second rebases.


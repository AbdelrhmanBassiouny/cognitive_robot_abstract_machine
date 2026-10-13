Item: actions-budget / budget-manifest. Draft PR #503 on #501 (claude/brave-archimedes-nonocl); retarget to main once #501 lands.
Plan: option A + cost rule (generic rules over workflow YAML; repo-owned .github/actions_budget.py defining actions_budget() with limits and per-workflow overrides; basstler writes the first version).
Done: review rounds 1-2 (7c46d7e1c, 750029682, 045a8a741 Python budget file + OverrideWithoutWorkflow); all 6 threads replied and resolved; 805 tests pass.
Next: user review; open for the user: default limits (60 min, 4 jobs), Examples on ready-opened PRs.

Item: actions-budget / budget-manifest. Draft PR #503 on #501 (claude/brave-archimedes-nonocl); retarget to main once #501 lands.
Plan: option A + cost rule (generic rules over workflow YAML; repo-owned .github/actions-budget.toml with limits and per-workflow overrides; basstler writes the first version).
Done: review round 1 complete (7c46d7e1c, 750029682); all 5 threads replied and resolved; 801 tests pass.
Next: thread r4261298505 (Python budget file instead of TOML) proposed, awaiting the user's choice; then implement + add the missing-workflow-file check. Open: default limits (60 min, 4 jobs), Examples on ready-opened PRs.

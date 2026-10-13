Item: actions-budget / budget-manifest. Draft PR #503 on #501 (claude/brave-archimedes-nonocl); retarget to main once #501 lands.
Plan: wait for the user's pick on the open review thread (manifest design: A generic rules over workflow YAML + repo-owned ceilings file [recommended], B basstler generates YAML, C hybrid), then rework #503 to it.
Done: review round 1 (7c46d7e1c): constants on classes, exceptions in basstler/exceptions.py; 4 threads replied+resolved; 791 tests pass.
Next: implement the chosen design; still open for the user: Examples on ready-opened PRs, timeout/runs-per-day numbers.

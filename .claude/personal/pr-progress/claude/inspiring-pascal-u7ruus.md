Item: actions-budget / budget-manifest. Draft PR #503, base main.
Plan (full version in the plan's roadmap.md, section "budget-manifest: settled plan"):
1. Tests first: test/basstler_test/test_actions_budget.py + small workflow fixtures in the dataset.
2. basstler/actions_budget.py (manifest + workflow dataclasses, violation types) and basstler/actions_budget.toml.
3. Workflow edits: timeout-minutes everywhere on runner jobs; examples on ready_for_review/full-ci label/dispatch;
   fork guard on push for ci, examples, docs, 4 publish workflows.
4. Format docstrings, run basstler tests, update PR description, re-draft.
Done: kickoff, branch, draft PR, manifest open/record.
Next: step 1.
Decisions: cancel-in-progress rule only for PR workflows running on synchronize; reusable callers carry no timeout;
fork guard on root jobs only; runs/day + timeouts are first estimates for the user to adjust.

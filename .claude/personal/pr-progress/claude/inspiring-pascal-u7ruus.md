Item: actions-budget / budget-manifest. Draft PR #503, base main. Head b66263166.
Done: manifest (basstler/actions_budget.toml), reader (basstler/workflows.py), budget + violations
(basstler/actions_budget.py), tests (test_actions_budget.py + dataset/actions-budget), workflow edits
(timeouts, examples on ready_for_review/full-ci/dispatch, fork push guard), README section, PR description.
basstler suite: 748 passed. actionlint: no new findings.
Decisions: cancel-in-progress only for PR workflows on synchronize; reusable callers carry no timeout;
fork guard on first jobs only; reader split from budget for convergence with #211's workflow_document.py.
Open for the user: Examples not running on ready-opened PRs (upstream impact); timeout/runs-per-day estimates.
Next: user review. Nothing else outstanding.

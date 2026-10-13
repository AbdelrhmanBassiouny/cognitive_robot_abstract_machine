Item: actions-budget / budget-manifest. Draft PR #503, now based on #501 (claude/brave-archimedes-nonocl,
basstler src layout) at the user's request. Head ebfab8687. Retarget to main once #501 lands.
Done: manifest/reader/budget under basstler/src/basstler/, tests, workflow edits, README, PR description.
Tests on #501 base: 767 pass, 23 fail; the same 23 fail on #501's own head here (not ours).
Decisions: cancel-in-progress only for PR workflows on synchronize; reusable callers carry no timeout;
fork guard on first jobs only; reader split from budget (converge with #211's workflow_document.py).
Open for the user: Examples not running on ready-opened PRs (upstream impact); timeout/runs-per-day estimates.
Promotion link for #501 handed to the user (not recorded on #501).
Next: user review.

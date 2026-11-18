This branch has no code changes. The session's work is KAOS-repositories/basstler#265
(branch review-triage-script-pull-request-url, stacked on #253's review-triage-binding-renames).

Plan
- review-triage.sh takes a PR URL and gives its clone an origin, so --mark-viewed works from a fresh clone

Done
- Script fix plus tests/review_triage/test_script.py (5 tests, run locally through Git Bash)
- End to end on cram2 PR 1019 from an empty home: 339 files marked viewed
- Draft PR #265 opened with labels bug-fix, new-feature, bug, release:minor

Next
- Wait for CI and review on #265; it merges after #253
- Separate decision: should mark-viewed default --workflow-repository to --repository

# PR #115: plan-updates-since.sh

Item `plan-updates-since-helper` in the `workflow-unification` plan.

## Done

- PLAN_STATE_SYNC_STAMP + record/read helpers in resolve-personal-notes-config.sh.
- session-start.sh stamps the notes-branch SHA unconditionally on every fetch, plus a
  summary line.
- New .claude/hooks/plan-updates-since.sh <plan-id> [--since <sha>]: diffs the plan
  directory since a baseline, prints tracking-issue comments newer than that commit's
  timestamp (gh CLI preferred, curl+GH_TOKEN/GITHUB_TOKEN fallback - not sourced from
  github-api.sh, which isn't on fork main yet, only on #107's branch).
- .gitignore + README.md updated.
- test_plan_updates_since_sh.py: 13 new tests (own minimal scratch-repo + stubbed
  gh/curl fixtures, since neither sibling's shared fixture has landed on main). All 29
  tests under .claude/hooks/tests pass. Verified live against the real personal-notes
  branch and tracking issue #102 - printed diff matched a manual `git diff` exactly.
- PR #115 opened as draft, subscribed to activity.
- plan.yaml/roadmap.md updated and saved (status: in_progress, pull_request_number:
  115); dashboard republished.

## Next

- Wait for CI (test_claude_dev_tooling) and any review comments on #115.
- Once approved, mark ready for review only when explicitly told to (personal-notes
  convention keeps PRs in draft otherwise).

## CI triage log

- 2026-07-31: `test_each_lib (semantic_digital_twin) / test` red on #115 - confirmed it
  fails identically on `main` at this PR's base commit (0fd14357, run 30577674356), same
  `test_world_sim_state_sync` assertion. Unrelated to this PR's `.claude/hooks/*`-only
  diff; `test_claude_dev_tooling` is green. Commented on the PR, no fix pushed. Watching
  for the base branch to recover.

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
- 2026-07-31 (after merging main): same test red again post-merge (head 01d112c0, run
  30626569507) - this time NOT a base-branch issue, since main's own CI at the current
  tip (82501888, run 30624144609) passed it cleanly. Genuine physics-timing flake in
  Mujoco's box-settling assertion, unrelated to this PR. Tried `rerun_failed_jobs`;
  blocked with "workflow already running" since `coraplex` was still mid-run. Commented
  on the PR; will retry the rerun once the run fully completes.

## Review round 1 (2026-07-31)

5 review comments from the repo owner, all pointing the same direction: eliminate
hardcoded strings duplicated between production and tests, move the inline `python3 -c`
snippet to a real file, use structured types (StrEnum/dataclass). Addressed in one
commit: new `.claude/hooks/plan_updates_since_support.py` (mirrors
`plan_manifest_tools.py`'s precedent for `save-plan.sh`) now owns every user-facing
message string, the `--since` option name (`PlanUpdatesSinceOption(StrEnum)`), and the
tracking-issue-comment JSON shape (`IssueComment` dataclass + `IssueCommentField`
enum, with `to_api_response()` as the inverse of `from_api_response()` so tests build
stub JSON from the same field names instead of hand-typing them). `plan-updates-since.sh`
now calls into that module for everything it used to print inline; the test file
imports the same constants/dataclass instead of retyping copies. All 29 tests still
pass; replied to and resolved all 4 review threads.

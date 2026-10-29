PR #534 (draft, base `main`). Upstream: cram2#826 (approved by Tigul, sunava, LucaKro before 6f126b5d4).

Plan
- `PullRequestLabelsRules` in `agent_rules.py`/`AGENTS.md`: agents set `api-break`/`new-feature`/`bug-fix`/`maintenance`; framework, `documentation`, `dev-tools` left to `.github/labeler.yml`.
- `pr_api_break_check.yml` (pull_request, griffe 2.4.1 vs HEAD^1, uploads `api-break` artifact) + `pr_api_break_label.yml` (workflow_run, PR looked up by head SHA, add-only).

Done
- 6f126b5d4: griffe check + label workflows, rules aligned with the labeler, `RepositoryFile.API_BREAK_CHECK_WORKFLOW`. Dry run vs main~30 works (~30 s).

Next
- User: copy fork PR title/description to cram2#826, reply to LucaKro, add `new-feature`; approvals may need re-requesting.
- Unverified on GitHub: actionlint not run here; label job only runs after merge to default branch.


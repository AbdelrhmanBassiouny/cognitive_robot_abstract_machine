Item basstler-package/basstler-repository-extraction. Work for AbdelrhmanBassiouny/basstler; standalone branch backed up on the fork as claude/jolly-gauss-l2pjrh (basstler history, not CRAM).

Plan
- Push filtered history: main = #501 tip; rewritten tooling branches (re-run filter-repo per roadmap section if the scratch mirror is gone).
- Push claude/jolly-gauss-l2pjrh to the new repo, open its draft PR against main. Tag v0.1.0 on merge.

Done
- 4 commits on main: plugin/project split + one per-user env ($BASSTLER_HOME) + git-tag install; project-owned .claude/basstler/stack.toml; reusable upstream-reviews workflow + CI; .claude dir created on demand. 752 tests pass; live session start verified.

Next
- Blocked: user installs the Claude GitHub App on AbdelrhmanBassiouny/basstler (pushes 403).
- Follow-ups for the PR description: CRAM-named defaults left (cram-notes.md path, cram2-link-sent label, local-code-review skill); docformatter not run.

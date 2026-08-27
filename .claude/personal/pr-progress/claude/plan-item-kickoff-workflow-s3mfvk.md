## Plan

Item `session-branch-base` of plan `workflow-unification` (track `stack-tooling`), PR #199,
draft, based on `main`, labelled `bug`. Reasoning in the plan's `roadmap.md` under
"Update 2026-08-27 (kickoff)".

The fork's default branch is `refs/heads/integration` (`899a04aac`), not `main`. The guard is
deliberately *not* a git-ancestry test - `main` moves, so every branch that has not merged it
recently would trip one, and it cannot tell a branch cut from `integration` from one legitimately
stacked on a parent. Its subject is the default branch itself.

## Done

- `configured_base_branch()` and `repository_default_branch()` in
  `resolve-personal-notes-config.sh`; `default_branch_name()` prefers the configured base when a
  branch by that name exists, and is otherwise unchanged.
- `check-setup.sh` `default_branch` row; fires live against this clone's real `origin`.
- Seven tests; 538 pass across the four CI directories (from 531). Three mutations each fail
  exactly the test naming them.
- Draft PR #199 opened, labelled `bug`, description written to match.
- Manifest: `branch`, `session`, `pull_request_number`, `status: in_progress`; kickoff section
  in `roadmap.md`; dashboard republished.
- Repaired **two** truncated notes in `plan.yaml`, both the same defect - an unquoted scalar
  containing ` #<number>`, so YAML treats the rest of the line as a comment.
  `session-branch-base` was losing 1474 of 1881 characters, `unfetched-parent-branches` 2590 of
  2641. Swept the whole manifest; nothing else is affected.

## Next

- **Blocked, and it is the user's click**: restore the fork's default branch to `main`. No `gh`
  here and no repository-settings tool in the GitHub MCP server. Until it is done,
  `check-setup.sh` exits 1 in this fork and every plan skill stops and offers a setup that
  cannot fix it - which is the guard working, and why #199 must not merge before the flip.

## Watch

- Overlaps textually with #188 on `resolve-personal-notes-config.sh` and `session-start.sh`'s
  test module, and with #185 on the first. Both open, both based on `main`; whichever lands
  second merges.
- No PR-activity subscription, and no scheduled check-ins - per personal notes. The
  tracking-issue subscription the kickoff skill asks for was refused by the permission
  classifier, so this session is not on that channel.

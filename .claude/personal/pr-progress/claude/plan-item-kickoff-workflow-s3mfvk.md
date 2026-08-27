## Plan

Item `session-branch-base` of plan `workflow-unification` (track `stack-tooling`), PR #199,
draft, based on `main`, labelled `bug`. Full reasoning in the plan's `roadmap.md` under
"Update 2026-08-27 (kickoff)".

The fork's default branch is `refs/heads/integration` (`899a04aac`), not `main`, so
`default_branch_name()` - which trusts `refs/remotes/origin/HEAD` - inverts `pr_progress_path`
and `branch_can_hold_plan_item`, and every session cloned from the fork starts on the wrong tip.

The guard is deliberately *not* the git-ancestry test the item's sentence suggests - `main` moves,
so every branch that has not merged it recently would trip such a test, and it cannot tell a
branch cut from `integration` from one legitimately stacked on a parent. Its subject is the
default branch instead.

## Done

- Setup gap closed: `markdown` and `nh3` installed; the other checks were already `ok`.
- Branch reset onto `main`, draft PR #199 opened and labelled `bug`, description written to
  match what landed.
- Manifest: `branch`, `session`, `pull_request_number`, `status: in_progress`; kickoff section
  appended to `roadmap.md`.
- Repaired the item's own `notes` in `plan.yaml`: an unquoted YAML scalar containing ` #64` meant
  every parser read 407 of its 1881 characters. Quoted; round-trip verified.
- `configured_base_branch()` and `repository_default_branch()` in
  `resolve-personal-notes-config.sh`; `default_branch_name()` now prefers the configured base
  when a branch by that name exists, and is otherwise unchanged.
- `check-setup.sh` `default_branch` row; fires live against this clone's real `origin`.
- Seven tests, 538 passing across the four CI directories (from 531). Three mutations each fail
  exactly the test naming them.

## Next

- **Blocked, and it is the user's click**: restoring the fork's default branch to `main`. No
  `gh` here and no repository-settings tool in the GitHub MCP server. Until it is done,
  `check-setup.sh` exits 1 in this fork and every plan skill stops and offers a setup that
  cannot fix it - which is the guard working, but it is why this must not merge before the flip.
- Republish the plan dashboard (the Artifact tool requires reading the live 1.1MB page first).

## Watch

- Overlaps textually with #188 on `resolve-personal-notes-config.sh` and `session-start.sh`, and
  with #185 on the first. Both open, both based on `main`; whichever lands second merges.
- No PR-activity subscription, and no scheduled check-ins - per personal notes.

## Plan

Item `session-branch-base` of plan `workflow-unification` (track `stack-tooling`), PR #199,
draft, based on `main`. Full reasoning in the plan's `roadmap.md` under
"Update 2026-08-27 (kickoff)".

The fork's default branch is `refs/heads/integration` (`899a04aac`), not `main`. Two live
consequences: `default_branch_name()` in `resolve-personal-notes-config.sh` trusts
`refs/remotes/origin/HEAD`, so `pr_progress_path` and `branch_can_hold_plan_item` suppress and
track exactly the wrong branches; and every session cloned from the fork starts on
`integration`'s tip.

The guard is deliberately *not* the git-ancestry test the item's sentence suggests - `main` moves,
so every branch that has not merged it recently would trip such a test, and it cannot tell a
branch cut from `integration` from one legitimately stacked on a parent. Its subject is the
default branch instead:

1. `configured_base_branch()` reads `upstream_base` from the personal `.claude/personal/stack.toml`
   override layered over the committed `.claude/stack/stack.toml`, by `grep`, and
   `default_branch_name()` prefers it when the branch it names exists - falling back to today's
   behaviour otherwise, so a repository with no stack configuration is unaffected.
2. A `default_branch` row in `check-setup.sh` reports `needs-setup` when the repository's own
   default branch disagrees with that base. That *is* the refusal to plan: every plan skill runs
   `prerequisite-check.md` first and stops on a non-zero exit.
3. Restore the fork's default branch to `main`, in the same pass - the guard would otherwise lock
   the plan skills out of a repository no session here can fix (`gh` is absent and the GitHub MCP
   server exposes no repository-settings tool).

## Done

- Setup gap closed: `markdown` and `nh3` installed; `check-setup.sh` exits 0.
- Branch reset onto `main`, bootstrap commit pushed, draft PR #199 opened.
- Manifest: `branch`, `session`, `pull_request_number`, `status: in_progress` recorded; kickoff
  section appended to `roadmap.md`.
- Repaired the item's own `notes` in `plan.yaml`: it was an unquoted YAML scalar containing ` #64`,
  so every parser (the dashboard included) read 407 of its 1881 characters. Quoted; round-trip
  verified.

## Next

- Tests first, then `configured_base_branch()` / `default_branch_name()`.
- Tests first, then the `check-setup.sh` `default_branch` row.
- Flip the fork's default branch to `main` and confirm the new check goes green.
- Fill in PR #199's description; keep it a draft.

## Watch

- Overlaps textually with #188 on `resolve-personal-notes-config.sh`, `session-start.sh` and
  `session-start-messages.sh`, and with #185 on the first. Both open, both based on `main`;
  whichever lands second merges.
- No PR-activity subscription, and no scheduled check-ins - per personal notes.

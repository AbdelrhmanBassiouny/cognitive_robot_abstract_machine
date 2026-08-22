## Plan

Make every session start from a fresh base: a deterministic SessionStart step that
fast-forwards the fork's default branch from the upstream repository, locally and on
the fork, and reports how stale the current branch is.

Live evidence at session start: `origin/main` was 86 commits behind
`cram2/main`, and this branch is exactly `origin/main`.

Design decisions:
- New `.claude/hooks/fast-forward-default-branch.sh`, run as a subprocess by
  session-start.sh (same shape as check-setup.sh), printing one summary line.
- Upstream repository/base resolved from `stack.py configuration`, the existing
  single source of truth, so no second place names the upstream.
- Fast-forward only, never a force push; a diverged default branch is reported and
  left alone.
- Only the default branch is touched. The current working branch is never merged or
  rebased automatically; its staleness is reported as an indented follow-up row.
- Never fatal: every failure path reports and exits 0.

## Done

- Explored the hook/test conventions and the stack configuration resolution.
- Confirmed the bug is live (86 commits behind).

## Next

1. Failing tests in `.claude/hooks/tests/test_default_branch_fast_forward.py`.
2. Implement the script + wording in session-start-messages.sh + the report line.
3. README, plan item on workflow-unification's personal-data track, dashboard.
4. Commit, push, draft PR with the `bug` label.

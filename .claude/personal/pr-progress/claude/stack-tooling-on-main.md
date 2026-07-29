## PR #106 - stack-tooling-on-main (workflow-unification plan)

**Plan:** see the approved plan-mode plan for this item (kickoff done via
/plan-item-kickoff workflow-unification stack-tooling-on-main). Ports the read-only
stack.py (status/check/next/restack-plan) from claude/stack-workflow-tooling to
.claude/stack/ on main, dropping the dead round-robin/stack-turn/WIP-cap subsystem,
adding personal-notes config layering, and bringing the code to AGENTS.md standards.
board.json export / board.html rendering deliberately deferred to PR 3/4 (user's
explicit choice during kickoff, over the item notes' literal "port everything").

**Done:**
- .claude/stack/{stack.py,stack.toml,ROUTINE.md,README.md,tests/} written and committed.
- resolve-personal-notes-config.sh + ci.yml wired with STACK_* constants.
- 237 tests passing (hooks + plan-dashboard + new stack tests); format_docstrings.py run.
- Branch pushed, PR #106 opened as a draft against claude/patch-pr-rheubx (PR #101).

**Next:**
- Subscribe to PR #106 activity and watch for CI/review.
- Flag on the PR (or fix directly if trivial): design decision 1 in roadmap.md looks like
  a stale cross-reference ("/setup-personal-notes (PR #101) already creates"
  .claude/personal/stack.toml - it's actually setup-stacked-prs-skill, PR 2).
- Once #101 merges, this PR's base should be retargeted to main per the routine's normal
  reparent-on-merge handling (or manually if that hasn't happened yet).

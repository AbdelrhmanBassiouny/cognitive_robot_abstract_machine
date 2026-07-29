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
- First CI run: all 20 checks green, mergeable_state clean.
- First review round (4 line comments from AbdelrhmanBassiouny) addressed and resolved
  (commit 1afebec3): dropped a stale `restack.js` mention from README's hygiene bullets,
  trimmed a krrood/ORM procedural block duplicating ROUTINE.md's Phase 2, removed the
  "board and restack workflow" section (roadmap info that belongs in the PR description,
  not the README), and reworded three stack.py docstrings that named "the routine" as a
  caller instead of documenting the contract (AGENTS.md convention).
- CI check `test_each_lib (semantic_digital_twin) / test` went red on commit 1afebec3
  (`test_world_sim_state_sync`, a MuJoCo settling-position assertion) - confirmed
  unrelated to this PR's `.claude/`-only diff and failing identically on the base
  branch (PR #101 / claude/patch-pr-rheubx). Noted on the PR as not mine to fix;
  waiting for the base to recover.
- Follow-up review comment: "via the GitHub MCP" in stack.py's module docstring still
  named a caller (anything with MCP access), the same issue as "the routine" from the
  first round. Dropped that clause entirely (commit 001b4f95) - the docstring doesn't
  need to say how board.json gets refreshed at all.

**Next:**
- Once semantic_digital_twin's test_world_sim_state_sync recovers on the base branch
  (PR #101), merge/rebase onto it so this PR's CI re-runs against the fixed base.
- Keep watching PR #106 for further CI/review activity.
- Flag on the PR (or fix directly if trivial): design decision 1 in roadmap.md looks like
  a stale cross-reference ("/setup-personal-notes (PR #101) already creates"
  .claude/personal/stack.toml - it's actually setup-stacked-prs-skill, PR 2).
- Once #101 merges, this PR's base should be retargeted to main per the routine's normal
  reparent-on-merge handling (or manually if that hasn't happened yet).

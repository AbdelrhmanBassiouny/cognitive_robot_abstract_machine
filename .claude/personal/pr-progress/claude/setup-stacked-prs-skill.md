# PR #110 — /setup-stacked-prs (plan item `setup-stacked-prs-skill`)

Branch `claude/setup-stacked-prs-skill`, based on `claude/setup-personal-notes-script` (#107).
Plan: `workflow-unification`, stack-tooling track, upstream wave. Tracking issue #102.

## Plan

Merged from two independently produced kickoff plans (one via `/plan-item-kickoff`, one from a
plain prompt). Deliver the stack-side counterpart of `/setup-personal-notes`, following #107's
script/skill split: `check-stack-setup.sh` (read-only), `setup-stacked-prs.sh` (all mechanical
steps, no session), `write-branch-files.sh` (the multi-file branch write the fork-overlay mode
needs), the skill plus its `prerequisite-check.md`, and a board-free `stack.py config` command.

## Done

- Step 0: #107 restacked onto #106 (base retargeted, #106 merged in) so the upstream wave is a
  linear chain. The diamond alternative was rejected: `stack.py restack-plan` derives exactly one
  parent per branch from the PR base, so a two-parent branch is invisible to the second parent.
- All five deliverables implemented TDD, 334 tests passing (was 320), network- and
  credential-free. Draft PR #110 opened and subscribed.
- Two gaps found and fixed on the way: `cram2-link-sent` was set/cleared by ROUTINE.md with no
  key in stack.toml; `board.json` was documented as never-committed scratch with nothing
  gitignoring it.
- `plan.yaml` + `roadmap.md` updated and saved; dashboard republished.
- Separately, on `claude/plan-item-kickoff-workflow-ylk9wu`: four improvements to
  `plan-item-kickoff`'s SKILL.md, from comparing the two kickoff plans. Pushed, no PR yet.

## Next

- Watch #110's CI (`test_claude_dev_tooling` is the relevant job) and drive it green.
- Self-review and un-draft when ready — that is the approval gate for promotion.
- Decide whether the SKILL.md improvements want their own PR; that branch touches a file #106
  also edits, so expect a small conflict when both land.
- Still unverified: live label creation, for the same token reason as #107.


## Plan: workflow/tooling unification (this session's deliverable)

Reviewed the distributed workflow tooling (routine, stack-workflow-tooling branch, session-hooks,
personal-notes + plan skills, stack-board repo, PR #101) and delivered an implementation plan in
chat (2026-07-29). Awaiting the user's approval; on approval run /plan-create workflow-unification.

Key findings: routine prompt duplicated+drifted in dev/README.md; restack.js dead (contradicts
routine, assumes local ROS); dev/README still says subscribe_pr_activity (contradiction);
stack-turn/round-robin machinery dead since wip_cap=1000000; claude/session-hooks superseded by
main (+1237/-6); cram-notes.md's EQL living roadmap ~10k tokens loaded every session; two dashboard
pipelines (board=Pages vs plans=Artifacts) with LOC/CI chips only on the board.

Plan (approved shape TBD): PR 1 stack tooling -> .claude/stack/ on main (stacked on PR #101 branch
claude/patch-pr-rheubx; port stack.py minus round-robin, generic ROUTINE.md, 1-page README, tests);
PR 2 /setup-stacked-prs skill (config-on-personal-notes recommended over per-user dev branch — drift
argument); PR 3 shared pr_state module + LOC/CI chips in plan dashboards; PR 4 stack-board Action
builds board + plan dashboards from main + personal-notes; then routine cutover to 10-line pointer;
personal-notes slimming (/plan-create eql-verbalization) can start immediately; retire
session-hooks now, stack-workflow-tooling after one green cycle.

Portability follow-up (user question, 2026-07-29): system must stay runnable on repos other than
cram2. Adjustments folded into the plan: PR 2's /setup-stacked-prs gets two install modes — native
(tooling on the target repo's main) and fork-overlay (skill creates/updates a never-merged tooling
branch on the user's fork from its own canonical files, for repos that won't take .claude tooling
upstream; re-running the skill is the drift-fix/updater). PR 4 parameterizes board.yml's hardcoded
fork repo/branch/upstream as repository variables. PR 1 rule: no repo names outside stack.toml
defaults + doc examples. Long-term option kept open (not now): lift into a standalone plugin/template
repo for per-user cross-repo install.

Next: user approval -> /plan-create workflow-unification -> dispatch PR 1 on claude/patch-pr-rheubx.

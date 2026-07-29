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

DONE 2026-07-29: plan approved and created — .claude/personal/plans/workflow-unification/
(9 items, 4 tracks, 3 waves), tracking issue #102 (subscribed), dashboard published:
https://claude.ai/code/artifact/36572776-4278-447a-8133-e087096b9cb8 (URL cached in
_generated/dashboard-urls.yaml). PR #101 now carries `in-review` (promoted to cram2).

Progress 2026-07-29 (late): PR 1 done as draft #106 (claude/stack-tooling-on-main). Both
immediate-wave items done by other sessions (eql-verbalization plan created; session-hooks branch
deleted by user — tag-push/branch-delete 403 from sessions, see roadmap addendum). Plan now 11
items: added setup-personal-notes-script (user prompt in roadmap.md) and
dev-tooling-python-package (package created in PR 3, migration last in upstream wave). NOTE: a
concurrent-save race clobbered the other session's manifest edits once (save-plan.sh is
last-writer-wins whole-file); merged and restored — refetch personal-notes before every save.

Next: PR 1 (#106) awaits self-review/un-draft; then PR 2/PR 3 dispatch; leftover
origin/claude/push-scope-test-zsq7jc needs out-of-harness deletion.

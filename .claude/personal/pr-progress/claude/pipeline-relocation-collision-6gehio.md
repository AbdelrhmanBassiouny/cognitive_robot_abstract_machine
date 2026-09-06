PR #285: Refuse a tip whose merge would take the pipeline out of the tree.

Status: done, opened as draft against PR #211's branch
(claude/plan-item-kickoff-workflow-unification-wg4w4x), labeled `bug`.

What happened: the scheduled Integration refresh was crashing 6 runs in a
row because #111 (the .claude -> bastler relocation) merges cleanly and
takes .claude/stack/integration.py etc. out of the assembled tree; the
existing CarriedPipeline guard only checks after assembly finishes, by
which point every subsequent step already runs against the broken tree.

Fix: IntegrationBuild.merge() now checks, after each merge/replay that
reaches the tree, whether any pipeline path present before is missing
after. If so it discards that merge (new
MaintenanceGitCommandRunner.discard_since, a git reset --hard) and reports
the tip SKIPPED with the same attribution a textual collision gets, so the
build carries on rather than publishing (or crashing on) a decapitated
tree.

Base-branch archaeology: this branch's files (integration_assembly.py,
integration_carried_pipeline.py) only exist on PR #211's branch
(wg4w4x), not on #154 or main - PR #211 is the real, live, currently-open
owner of this code, confirmed by content hash comparison after an early
false start where I nearly mistook 18 of #211's own commits for
unreviewed direct pushes to `integration` (I hadn't fetched enough
branches to see they were ancestors of real open PRs). Branched off
origin/integration per the task's explicit instruction, then rebuilt the
branch from wg4w4x once the correct base was confirmed.

Tests: added test_a_tip_that_would_take_the_pipeline_out_of_the_tree_is_skipped
and test_a_build_continues_past_a_tip_that_would_remove_the_pipeline to
tests/test_integration_build.py (TDD - both fail against the pre-fix
code). Full suite on this branch: 549 passed.

Next: nothing outstanding from this session. Per personal notes, this
session's obligation ends now that the draft PR is open - no subscription,
no scheduled check-in. If CI or review comments come in, they'll need a
prompt to be picked up.

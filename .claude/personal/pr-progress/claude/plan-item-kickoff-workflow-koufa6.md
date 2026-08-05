## claude/stacking-branch-switch-issue-v1kzqq - stack tooling vanishing on branch switch

**Outcome: folded into PR #139 (`claude/plan-item-kickoff-workflow-koufa6`).** Two commits:
`c70506567` (worktree + skill recovery) and `895baca6c` (detach the caller's branch). The
designated branch was never used - the fold test pointed at #139, since
`.claude/stack/maintenance.py` exists only there.

**Root cause:** `.claude/stack/` is tracked content and `restack` switched branches in the
checkout carrying it. 126 of 146 fork branches predate the tooling merge. Second defect, same
cause: step 0's `git checkout <ref> -- .claude/stack/` writes the index, so the tooling would
ride a restack merge commit into a feature branch and upstream.

**Shipped:** `RestackWorktree` (detached worktree outside the project, owned by `restack`);
`DetachedCheckout` (lends the caller's branch for the pass); `SKILL.md` on
`git restore --source=<ref> --worktree`; 8 new tests, 148 passing (was 140).

**Lesson worth keeping: this sandbox runs git 2.43, CI runs 2.54.** 2.43 lets `checkout -B`
take a branch another worktree holds; 2.54 refuses. My local probe said the collision was a
silent quirk, CI said hard failure on five tests. Do not settle a git-behaviour question from
this sandbox's version alone - and prefer a test that asserts the invariant (version-independent)
over one that depends on git's refusal.

**One existing test changed** - `test_an_integration_stopped_before_it_began_is_not_reported_as_a_conflict`
kept every assertion, swapped its cause from an untracked file in the caller's checkout
(unreachable now) to unrelated histories. Called out on the PR since the repo rule forbids
modifying failing tests.

**Left for the developer, raised on the PR, not acted on:** #139's description carries a literal
`## Promote` heading at line 50, so a future `promote` would delete both correction sections
below it.

**Not subscribed to #139.** Not this session's PR, and already marked ready by the developer.

**CI:** `test_claude_dev_tooling` green on `895baca6c`. Nothing pending; work on #139 is done.

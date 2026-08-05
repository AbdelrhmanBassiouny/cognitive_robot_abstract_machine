## claude/stacking-branch-switch-issue-v1kzqq - stack tooling vanishing on branch switch

**Outcome: folded into PR #139 (`claude/plan-item-kickoff-workflow-koufa6`), pushed as
`c70506567`.** The designated branch was never used - the fold test pointed at #139, since
`.claude/stack/maintenance.py` (which does the branch switching) exists only there.

**Root cause:** `.claude/stack/` is tracked content and `restack` switched branches in the
checkout carrying it. 126 of 146 fork branches predate the tooling merge, so this fired on
nearly every pass. Second defect, same cause: step 0's `git checkout <ref> -- .claude/stack/`
recovery writes the index, so the tooling would ride a restack merge commit into a feature
branch and then upstream.

**Shipped:** `RestackWorktree` (detached worktree outside the project, owned by `restack`
so no caller can forget it); `SKILL.md` switched to `git restore --source=<ref> --worktree`;
5 new tests, 145 passing (was 140). `board.json` was already gitignored on #139.

**One existing test changed** - `test_an_integration_stopped_before_it_began_is_not_reported_as_a_conflict`
kept every assertion, swapped its cause from an untracked file in the caller's checkout
(unreachable now) to unrelated histories. Called out on the PR since the repo rule forbids
modifying failing tests.

**Left for the developer, raised in the PR comment, not acted on:**
1. A stack branch checked out in the invoking checkout still moves under it (`checkout -B`
   skips the already-checked-out guard). Would be a new pre-flight refusal - scope creep.
2. #139's description carries a literal `## Promote` heading at line 50, so a future
   `promote` would delete both correction sections below it.

**Not subscribed to #139.** It is not this session's PR and it was already marked ready by
the developer, so its job had ended; the fold was a one-off on request.

**Next:** nothing pending unless CI on #139 comes back red.

## claude/plan-item-kickoff-workflow-koufa6 (PR #139) - resolve of 2026-08-12

**Done, pushed, nothing outstanding for this session.** Two commits: `614eaccd` (merge of
`main`) and `ba674d1d` (the review round of 2026-08-11).

**Plan:** merge fork `main`, answer the four unanswered review threads, repair the
description, write the manifest/roadmap, republish the dashboard, broadcast on #102. All
done.

**The blocker was the fast-forward, not the pull request.** An earlier resolve the same
morning had measured the SKILL.md conflict as latent (against cram2 `main`, not fork
`main`) and deferred it. Fork `main` was fast-forwarded hours later, so the conflict became
live against #139's own base and a maintenance pass labelled it `needs-resolution`. The
prediction held exactly - same single file - so the deferral cost nothing.

**The conflict:** `main`'s side was 2 lines (`no-pr-subscriptions`, #153/upstream #535,
rewording the conflict-report step); this branch's side was a 117/134-line rewrite of the
same document. Kept ours, folded `main`'s surviving instruction - *write the comment to
stand alone* - into the red-check bullet, the one place that still asks a person to write
such a comment. Merge, not rebase: #151 and #154 are both based on this branch and now
need a restack.

**Review round applied:** the `_s` on a test name was a possessive that lost its apostrophe;
two test-local stand-ins were plain classes among frozen dataclasses. Left open on the
user's call: why the abstract-command refusal is a `TypeError` - it is `ABCMeta`'s, and a
custom error means dropping the abstractness chosen in the previous round.

**Lesson worth keeping: `scripts/format_docstrings.py` reporting no change is not evidence
a file is formatted.** It reports no change on `maintenance_board.py` while
`docformatter --check` disagrees on 33 docstrings, because the script keeps the black-only
content whenever docformatter's result does not survive a second black pass - one blank
line after an attribute docstring preceding a decorated definition. Five files were
silently on the wrong side, not the one flagged. Fixed as `black` -> `docformatter` ->
`black`, which is stable (re-running the script returns them byte-identical). `stack.py` is
in the same state and left alone as `main`'s file - and that also answers the earlier
thread's open half: `main`'s unformatted files are not neglected, they are the ones the
formatter cannot converge on.

**The `## Promote` hazard the previous session left for the developer has now fired**, and
is fixed. The description had been truncated at that literal heading by
`description_with_promotion_link`, taking the live-fork evidence bullets with it - and the
session link, which is why the 09:49 conflict comment said "This pull request's description
names no session to address" and reached nobody. Rewritten without a partitionable heading,
session link restored.

**450 tests** across the three directories CI runs. Not re-drafted: the developer marked
this pull request ready themselves on 2026-08-05. `needs-resolution` deliberately left for
the next pass to clear itself, since that loop is what this item exists to close.

**Not subscribed to #139**, and no check-ins armed.

---

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

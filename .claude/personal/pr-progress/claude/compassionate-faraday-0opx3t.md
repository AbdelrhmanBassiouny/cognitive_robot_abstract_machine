## claude/compassionate-faraday-0opx3t - PR #482 (bug fix, draft)

Plan item: workflow-cutover / maintenance-rereport-fix. Split out of resolving
routine-cutover (#280) at the user's choice, 2026-10-02.

**Bug:** WithholdBranchStillConflicting trusted GitHub's mergeable_state alone,
so a branch GitHub read as mergeable but whose derived parent still conflicted
got its needs-resolution label cleared, re-merged, re-conflicted and
re-commented on every run (91 comments on #156, 2026-09-19..30).

**Done:**
- Failing test first: test_a_branch_github_reads_as_mergeable_is_withheld_while_its_parent_still_conflicts
  (outcome `conflict`, expected `withheld`).
- Fix (aaae95f2f): withhold while GitHub says dirty OR a trial integration of
  the parent leaves unmerged paths; integration moved onto
  BranchUnderRestack.integrate_parent()/parent_still_conflicts().
- .claude/stack/tests: 155 passed. Draft PR #482 opened, labels bug + tooling.

**Next / outstanding:**
- CI on #482 not checked yet.
- #185 moves this module into basstler/; whichever lands second re-applies
  the change there (#280 already sits on #185 and does not carry this fix).
- Should land before routine-cutover deletes the Routine trigger.

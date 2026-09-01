## PR #162 — promotion-summaries-and-table (stack-maintenance)

Resolve run of 2026-09-01. The item was recorded `in_progress` while the pull request had in
fact been withheld from promotion since 2026-08-31 by the `integration-conflict` label.

### What was wrong

- **The block.** `PendingPromotionsCommand` named itself with `class_property.classproperty`.
  #151 deletes that module when it moves the command base to `.claude/shared/command_line.py`.
  The class is text only this branch has, so the two merge with no conflict and the merged tree
  fails at import. Reproduced by merging and running the configured integration suite.
- **An unanswered question.** The dataclass-exception review thread asked on 2026-08-31 whether
  the rebase onto #151 is worth it now that #151 is no longer behind `main`.

### Done

- Failing test first (`test_the_pending_promotions_command_declares_itself_with_ordinary_properties`),
  then the fix: the command declares `invoked_as`/`description` as ordinary properties, and the one
  test reading the name off the class reads it through an instance. `a2a9794cb`.
- Placed the new test between two tests #151 leaves byte-identical. The first placement merged into
  a *conflict* — a loud failure in place of a silent one, which fixes nothing.
- 579 pass on the branch, 697 on the tree merged with #151, no conflict.
- `integration-conflict` label removed; break-fixed comment posted on #162.
- Rebase question answered on its thread and **left open** for the user — the outcome is a
  deferral, not a change.
- Manifest: blockers recorded, then cleared; status back to `in_progress`; roadmap section added;
  description rewritten (plan/track name, the break, the figures).

### Next

- CI on `a2a9794cb` was still running when this turn ended. Nothing else is outstanding on the
  branch.
- The pull request is **left out of draft**: on this stack, un-drafting is how a branch is approved
  for upstream review, so re-drafting it would withhold it from promotion again — the opposite of
  the resolution.
- Still open on the item itself, untouched by this run: whether an already-registered scheduled
  run's notification setting can be changed in place.

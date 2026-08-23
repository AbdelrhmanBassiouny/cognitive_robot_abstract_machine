**Session: `/plan-item-resolve rdr-refactor D-core-aid` (PR #63, branch `D-core-aid`).**
This session's own branch carries no commits; the work went to the item branches, with
explicit permission.

1. Fork review threads: all seven resolved, each with its own reply. **Done.**
2. ~~Restore the `## Promote` section~~ - **wrong, reverted.** `/upstream-reviews` (which I
   had skipped, on the label rule) shows the branch was already promoted as cram2 **#557**.
   Label corrected to `in-review`, `cram2-link-sent` cleared, `## Promote` removed.
3. **#557's naming thread implemented** - `ConclusionHelper` base + `ConclusionSupportPresenter`
   / `ConclusionSuggester` mixins, `aid.py` -> `conclusion_helper.py`. Four branches in one
   round: #63 `39da5f22`, #67 `04a3fe89`, #98 `af77399b`, #159 `34df6172`. All pushed.
4. Records: four items' notes, roadmap sections 27 and 28, #94 (three comments, the second
   correcting the first), dashboard republished. **Done.**

Outstanding, none of it started:

- **CI on the four pushed branches was still running when this turn ended.** Not watched, per
  the standing rule; check it when you look.
- **LucaKro's dead-code review on #557 is unanswered** - yours, as you said. The fact that
  answers it: `present()` has no production call site anywhere in the stack; `suggest()` does.
- **#67 tracks `test/krrood_test/dataset/ormatic_interface.py`**, which every other branch
  untracked, so `D-core-aid` merges into it modify/delete. Pre-existing (reproduced against
  the pre-round origin versions), probably what its `needs-resolution` label records, and
  exactly what `AGENTS.md` forbids. Not fixed - it is #67's own item.
- Two `.claude/stack` defects, `workflow-unification`'s `stack-tooling` track, still with no
  item: `promotion_summary()` returns the leading markdown heading, and a session cannot write
  a prefilled create-link.
- **The `in_review_label` is a single point of failure.** Three mechanisms read it to know a
  branch is under upstream review; it is set by hand at promote time, and one missed click hid
  #557 from all of them, including the check meant to notice.

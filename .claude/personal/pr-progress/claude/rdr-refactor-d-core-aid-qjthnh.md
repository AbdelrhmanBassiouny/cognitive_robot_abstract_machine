**Session: `/plan-item-resolve rdr-refactor D-core-aid` (PR #63, branch `D-core-aid`).**
This session's own branch carries no commits.

1. Reply to and resolve the three review threads the 2026-08-22 round left open. **Done** -
   all seven fork threads resolved, each with its own reply naming `c21e1fe3`.
2. ~~Restore the `## Promote` section~~ - **wrong, and reverted.** The developer asked whether
   the `upstream-reviews` Action had been run; it had not, and it shows the branch is already
   promoted as cram2 **#557**. The missing section was spent, not lost. `## Promote` removed,
   label corrected to `in-review`, `cram2-link-sent` cleared.
3. Records: item `notes` + `session`, roadmap section 27 and its same-day correction, tracking
   issue #94 (posted, then corrected), dashboard republished. **Done.**

Outstanding, and now the item's real work:

- **cram2 #557 has changes requested.** LucaKro: "this code is not used anywhere but the tests,
  so to me this is dead code". tomsch420: changes requested, no body. One unresolved thread on
  `aid.py:27` about the name `Aid`, where the developer settled the design: a `ConclusionHelper`
  abstract base plus one mixin per method (`ConclusionSuggestor` and a presenting counterpart),
  each mixin itself a `ConclusionHelper`. Not started - waiting on the developer's word, since
  it renames this item's own subject and this session was told to develop on its own branch.
- Two `.claude/stack` defects, `workflow-unification`'s `stack-tooling` track, neither with an
  item: `promotion_summary()` returns the leading markdown heading, and a session cannot write
  a prefilled create-link (it is neutralised into inline code).
- **The label is the single point of failure.** Three mechanisms read `in_review_label` to know
  a branch is under upstream review, and it is set by hand at promote time. One missed click
  hid #557 from all of them.

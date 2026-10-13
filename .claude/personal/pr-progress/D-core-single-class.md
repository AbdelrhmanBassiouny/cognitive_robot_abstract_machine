## Outstanding — the developer's
- **Seven threads still open**, none answered yet: `condition`/`conclusion` as `CaseContext`
  fields (I proposed a `ProposedRule` object instead, or reusing `RuleAnswer`); the
  `_splice_rule` rename (proposed `_attach_rule`, and `_insert_rule` → `_add_rule`);
  `Optional[List]` vs empty tuple for `targets` (proposed splitting `fit` /
  `fit_by_labelling` instead); the labelling-path convergence **defect**; the convergence
  detection follow-ups; and the `conditions_root` findings.
- **The labelling-path defect is still unfixed and is a silent wrong answer.** `fit` without
  targets never re-checks, so a later rule contradicts an earlier label with no error.
  Reproduced. Three options on thread `r3838361318`.
- **A saver that fails for a reason other than an empty tree still masks the fit's own
  exception**, because a raising `finally` wins. Stated on the saver thread; catching it to
  hide it is what AGENTS.md rules out, so it needs a decision.
- **CI has queued nothing** on #98 since `82eb69fb` or #159 since `04dc904c`. §21's
  base-move-then-push remedy has now been applied three more times without effect. #67 is the
  control — same stack, and it does run.
- #159 stays a draft. #98 and #67 were **not** re-drafted (developer-marked-ready).
- #67 still tracks `ormatic_interface.py`, which regenerated twice during this round and once
  blocked a stash pop. Its own defect, unfixed.

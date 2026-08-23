**Session: `/plan-item-resolve rdr-refactor d-core-single-class` (PR #159).** Mode: `auto`.
Work spans #67, #98 and #159; the harness branch stays unused.

## Round 1 — the review round applied

30 threads opened 2026-08-23 09:48–18:41Z, none answered. 18 applied and resolved, 12
answered and left open. Pushed `747b4045` + `9cf87496` on #159, `4832ec49` on #98.
Roadmap §29.

## Round 2 — the developer's answers implemented

Five of the twelve answered (four directly, one by implication); all five implemented.

| PR | commit | what |
|---|---|---|
| #67 | `54502f99` | `ZooDataset`; four modules to pytest |
| #98 | `9960a3d0` + merge | resolver takes the RDR; the shared gate; `TemporaryModelSaver`; three modules to pytest |
| #159 | `e4f0811f6` | save-when-the-fit-ends; `TemporaryModelSaver` default; engine side of the resolver |

New item `pytest-conversion-sweep` added for the modules outside `test_eql_rdr`.
`D-ui`'s notes carry the progress-bar default. Roadmap §30.

`test_eql_rdr` 232 → 244, zero baseline ids lost. `test_eql` 1167 passed / 3 skipped.

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

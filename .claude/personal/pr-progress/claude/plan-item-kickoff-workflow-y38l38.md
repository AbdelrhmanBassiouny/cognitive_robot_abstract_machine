# PR #162 — promotion-summaries-and-table (workflow-unification, stack-tooling)

Branch `claude/plan-item-kickoff-workflow-y38l38`, based on `claude/stack-tooling-pinning-qf5r2m` (#158).
Kicked off straight to implementation at the user's request; no plan-mode approval round.

## The plan

1. **Summaries file.** JSON keyed by fork pull request number, one entry per branch:
   `points` (a list — bullets are rendered by the script, so "point-based" is mechanical)
   and an optional `title` override. `PromotionSummary` / `PromotionSummaries` in
   `maintenance_promotion.py`, with `from_json` doing the reading. Delete
   `promotion_summary` (the first-paragraph derivation) rather than keeping it as a
   fallback — a fallback makes the new interface optional and today's defect reachable.
2. **Awaiting a summary.** `promote` returns a `PromotionRound` of what it promoted plus
   every `BranchAwaitingSummary`. New report field, new exit status
   `AWAITING_PROMOTION_SUMMARY = 11`, ranked below every existing non-clean status.
   `--summaries <file>` on both `promote` and `run-report`.
3. **`pending-promotions` command.** Reads each pending link back out of the fork
   description under `## Promote` (`promotion_link_in`, the inverse of
   `description_with_promotion_link`) rather than rebuilding it, and emits one markdown
   row per pending promotion: number, title, branch, link.
4. **`SKILL.md`.** New status row; the write-bullets-then-`promote` step; Finish section
   rewritten around the table, with the "a scheduled run emails its summary, so the
   summary *is* the delivery" premise withdrawn. Every new command written as `<pinned>/…`
   — #158's test asserts nothing else runs from the working tree.
5. **Fold onto #155.** The "turn its completion email on" paragraph exists only on #155's
   branch (unlanded, `cram2-link-sent` without `in-review`, so no upstream PR yet). Its
   reversal is pushed there, not carried on #162.

TDD throughout: every part above gets its failing test in
`.claude/stack/tests/test_maintenance.py` (or `test_maintenance_skill.py`) first.

## Done

- Branch created off #158, draft PR #162 opened.
- Manifest: `branch`, `session`, `pull_request_number`, `status: in_progress` recorded;
  roadmap section appended (kickoff entry of 2026-08-13).
- Dependency readiness checked with `check_dependency_readiness.py`: #139 merged, #158
  open and out of draft — both ready.
- Open question answered from the tool surface: `create_trigger` takes `notifications`
  (`{}` opts out of every channel), `update_trigger` has no notification field, so an
  already-registered Routine has to be re-registered to change it.

## Next

- Steps 1–5 above, in order.
- Republish `/plan-dashboard workflow-unification` after the manifest write.
- Note: `subscribe_pr_activity` on tracking issue #102 was refused by the permission
  classifier this session, so this session is not subscribed to it.

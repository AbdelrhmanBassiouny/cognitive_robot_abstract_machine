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

- Steps 1–4 implemented and pushed as `93edfb17`; PR #162 description rewritten to match.
  487 tests pass across the three CI directories. Mutation-checked in both directions:
  restoring the first-paragraph fallback fails the awaiting-summary test, dropping the new
  status fails the exit-status one.

- Step 5 done. Asked rather than guessed, because the roadmap said to fold the reversal
  into #155 while the notes' "a PR I marked ready myself is finished" rule said not to push
  to it. The user's answer settled it — "no emails and no notifications at all, a clear
  session summary; if that is doable in 155 then do it". Pushed `21599cca` to
  `claude/routine-prompt-refresh-ps5l3z`: notifications off, with the reason (the links
  outlive the run in each fork PR's description, and `pending-promotions` rebuilds the
  table), plus the tool fact that `update_trigger` has no notification field so an existing
  Routine must be re-registered. Left ready rather than re-drafted, per that same rule.
- One self-inflicted defect, found and fixed: rewriting #155's description dropped its
  `## Promote` section, which is exactly the illegal state this PR's own
  `RecordedPromotionLinkMissingError` refuses. Restored the original link verbatim, then
  verified it end to end by reading it back through this PR's own `promotion_link_in`
  against the live API. Worth carrying: a whole-body description write silently discards
  a section written by the promotion pass, so read the current body before replacing it.
- Dashboard republished at the same URL; no drift, nothing auto-corrected.

## Review round, 2026-08-13 (11 threads, `c5f174d2`)

- **A summary no longer gates a promotion.** User's call, and the reason is `routine-cutover`:
  the Action it ends on has no model, so requiring written points would leave it unable to
  promote at all. Both halves optional; no entry → body is just the fork-PR link.
  `EmptyPromotionSummaryError` and the `awaiting-promotion-summary` status deleted. Writing
  the summaries moved to SKILL.md step 2, *before* the pass, off `stack.py next --porcelain`.
- **Promotion reports per branch**, mirroring the restack half: `BranchPromotion` +
  `PromotionOutcome` (promoted / already-linked / withheld / link-label-cleared). Not a
  `BranchStatus` member — that model is derived from the board, and a written summary is not.
- **`GitHubLinks`** is the one statement of every github.com URL; `stack.py` composes through
  it. The read-back pattern is derived from the builder, so a link must now name the
  configured upstream and base — any `https://` URL qualified before.
- Upstream title convention recorded: `[TopicName] Catchy Minimal Relatable Title`.
- 486 tests pass; three mutations checked. 7 threads resolved, 4 left open (the two on the
  shared dataclass-exception base — deferred to whichever item lands `.claude/shared/`, since
  #151 is 159 commits behind main — and the two on `or`, which were answered, not changed).

## Next

- Nothing outstanding on #162 itself. It is a draft, mergeable against #158, CI on `c5f174d2`.
- Note: `subscribe_pr_activity` on tracking issue #102 was refused by the permission
  classifier this session, so this session is not subscribed to it.

**Session: `/plan-item-resolve rdr-refactor d-core-single-class` (PR #159, branch
`D-core-single-class`).** Mode: `auto`. Work went to the item branch and to #98; this
session's own harness branch `claude/rdr-refactor-d-core-single-xbadko` stays unused
(roadmap §15/§20 precedent).

## What was stalling it

A review round on 2026-08-23, 09:48–18:41Z, submitted 18:45Z against head `34df6172`:
**30 threads, none answered.** The item's notes, written hours earlier by §28, never
recorded it. Nothing else was wrong — dependency `open_ready`, base merging clean,
228 passed / 0 failed.

## Done

1. **18 threads applied and resolved**, each with its own reply naming the commit.
2. **12 design questions answered on their threads and left open** — the standing rule
   that a thread asking a question is the developer's to close.
3. **Pushed:** `747b4045` + merge `9cf87496` on #159; `4832ec49` on #98 (the
   `returns_ellipsis` rename, which belongs to the file's owner — doing it on #159 alone
   conflicted against #98 on the next merge).
4. **Records:** roadmap §29, both items' notes, PR #159 description rewritten, dashboard
   republished, #94 commented.
5. `test_eql_rdr` **228 → 232 passed**, zero baseline ids lost; `test_eql` 1167 passed /
   3 skipped. Mutation-checked: branch assertions, reachability, memorisation, convergence.

## Outstanding — all of it the developer's

- **12 open threads.** The ones with real weight: whether the condition resolver should
  take the context and fetch its own condition sets (I proposed a callable on
  `CaseContext` over handing it the RDR); whether `condition`/`conclusion` become
  `CaseContext` fields (I proposed a `ProposedRule` value object instead, because the
  retry loop reassigns the condition and `CaseContext`'s immutability is now load-bearing
  for `ExpertCall`); the `_splice_rule` rename (proposed `_attach_rule`, and `_insert_rule`
  → `_add_rule`); `TemporaryModelSaver` as the default saver; and the pytest conversion of
  the seven remaining files, which belong to #98 and #67.
- **A real defect, reproduced and not fixed.** `fit` without targets never re-checks, so a
  rule written for a later case silently contradicts the label the expert gave an earlier
  one. The same input with targets raises. Three options on thread `r3838361318`; the fix
  changes what a labelling fit costs a human, so it needs the developer's call.
- **CI has queued nothing** on #159 since `04dc904c` (2026-08-13) or on #98 since
  `82eb69fb` (2026-08-12). §21's base-move-then-push remedy was applied deliberately this
  round and did not clear it. Not repo-wide — `D-core-aid` and #64/#65/#66 all ran on
  2026-08-23. Both silent branches read `mergeable_state: unknown`.
- #159 stays a **draft**. #98 was **not** re-drafted (the developer marked it ready).

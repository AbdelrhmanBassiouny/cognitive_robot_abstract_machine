# PR plan: rdr/architecture-brief — re-land the design brief (Wave 0, S3)

Re-lands closed PR #20's content as a small docs-only PR off `main`.

## Plan

1. Cherry-pick `krrood/doc/eql/developer/rdr_architecture_plan.md` and the
   7 BibTeX entries from `rdr/oo-plan`.
2. Refresh stale parts: scope + §3 repo mapping point at the real post-split
   `krrood/src/krrood/entity_query_language/rdr/` package; §2.1 references
   `rdr/serialization.py`; remaining `eql_rdr` mentions renamed.
3. Wire the page into `doc/eql/developer/index.md` and `doc/_toc.yml`.
4. Verify: jupyter-book build warning-clean for the new page; docformatter
   (no Python files touched, so nothing to format).
5. Draft PR `rdr/architecture-brief` -> `main`, session link, subscribe.

## Done

- Branch `rdr/architecture-brief` cut from `origin/main`.
- Doc + 7 bib entries cherry-picked from `rdr/oo-plan`.
- Stale references refreshed (scope line, §2.1, §3 table, §4/§5/§7).
- Page wired into developer index and `_toc.yml`.
- Full jupyter-book build passed; new page warning-clean (all 280
  warnings pre-existing autoapi/notebook ones, none on touched files).
- docformatter: nothing to do (no Python files touched).
- Committed (ee4c9d57, authored as the user), pushed, draft PR #75
  opened with session link; subscribed to PR activity.

- 2026-07-16 ~20:45 check-in: steward session merged main into the
  branch (c4831fbb, "restack: upstream advanced"); CI fully green on
  the restacked head (18/18 checks), mergeable state clean, no review
  or conversation comments. Still draft, awaiting review.
- 2026-07-17 ~12:40 check-in: second steward restack (7d1cf8f5,
  "upstream advanced to cram2 #452"); CI 17/18 green, coraplex job
  still running. No comments. Still draft, awaiting review.
- 2026-07-17 ~13:40 check-in: coraplex job finished; CI fully green
  (18/18) on 7d1cf8f5, mergeable state clean. No comments. Still
  draft, awaiting review.

## Next

- Babysit PR #75: react to CI results and review comments; hourly
  send_later check-ins until merged/closed.

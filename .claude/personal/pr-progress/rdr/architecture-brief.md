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

## Next

- Await jupyter-book build result; confirm no warnings for the new page.
- Commit, push, open draft PR, subscribe to its activity.

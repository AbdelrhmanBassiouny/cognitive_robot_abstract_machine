# PR plan: rdr/architecture-brief — re-land the design brief (Wave 0, S3)

Not started. Recovers closed PR #20's content as a small docs-only PR off
`main`. Independent of everything; do first.

## Scope

- `git checkout abdel/rdr/oo-plan -- krrood/doc/eql/developer/rdr_architecture_plan.md`
  plus the 7 BibTeX entries it cites (PR #20 added them to
  `krrood/doc/references.bib` — cherry-pick from `abdel/rdr/oo-plan`).
- Update the doc's stale bits before landing: §3 repo mapping now points at
  the real `entity_query_language/rdr` package (post split), and §2.1's
  "same auto-serialization pipeline" claim should reference
  `rdr/serialization.py`.
- Wire into the developer doc index if `doc/eql/developer/index.md` lists
  pages explicitly.

## Procedure

Branch off `main`, docs build check (sphinx warnings clean for the new
page), draft PR to `main`.

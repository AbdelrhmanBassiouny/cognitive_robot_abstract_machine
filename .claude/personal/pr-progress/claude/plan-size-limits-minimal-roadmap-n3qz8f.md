## plan-size-limits / minimal-roadmap-writing — PR #279

**Plan:** Add `roadmap-writing.md` (keep/compress rule, mirroring
`manifest-staleness.md`'s shape), a `ROADMAP_WRITING_DOCUMENT` constant, and
one citation each in `plan-create`, `plan-item-kickoff`, `plan-item-resolve`
and `add-plan-item` at the point each writes roadmap text. Guidance only, no
enforcement (that's `refuse-oversized-save`), so based on `main` rather than
stacked on #207 — checked that every edit applies unchanged to `main`'s copy
of each file before cutting the branch.

**Done:**
- `roadmap-writing.md` written; doesn't restate the budget's own numbers.
- `plan-create/SKILL.md` migration guidance no longer says "preserve its
  detail rather than compressing it away."
- `plan-item-kickoff`, `plan-item-resolve`, `add-plan-item` each cite the
  document at their roadmap-writing point.
- `test_roadmap_writing_document.py` (derives bound skills the same way
  `test_manifest_staleness_document.py` does — mentions `roadmap.md` +
  a plan-writing script constant).
- Pushed, PR #279 opened as draft, manifest updated (`open`+`record`),
  roadmap section appended, dashboard republished. 405 tests pass.

**Not done / outstanding:** nothing outstanding. CI not yet checked on the
pushed commit — watch for it if asked to follow up.

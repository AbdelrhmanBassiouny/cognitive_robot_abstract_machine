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
- Review round (2026-09-06): 3 comments, all on `test_roadmap_writing_document.py`
  hardcoding literals that already have a shared home in `plan_item_bootstrap.py`.
  Fixed 2 (`HookScript.CONFIGURATION.path` for the config script path,
  `PlanDocument.ROADMAP` for `"roadmap.md"`), pushed as `0d105181ec`, replied and
  resolved both threads. Third (`"SKILL.md"` glob) has no existing shared constant
  anywhere in the codebase — replied with the precedent, left the thread open for
  a decision rather than resolving. PR description updated to match.

**Not done / outstanding:** the `"SKILL.md"` thread is open pending the reviewer's
call on whether a codebase-wide constant is worth a follow-up. CI not yet checked
on the pushed commits.

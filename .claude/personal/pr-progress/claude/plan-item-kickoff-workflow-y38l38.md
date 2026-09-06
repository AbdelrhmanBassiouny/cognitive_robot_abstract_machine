# promotion-summaries-and-table (#162) - resolve of 2026-09-06

## What was wrong

The manifest said `in_progress` with no blocker; GitHub said `dirty`. #158, the base this
branch is stacked on, had been rebased onto the `bastler` package move, so this branch's
delta still sat at `.claude/stack/`. Nine files conflicted. CI was green (23/23) and both
dependencies read ready, so the conflict was the only thing stopping it. A maintenance pass
reported the same nine files and labelled the branch `needs-resolution` at 18:08 the same day.

## Done

- Recorded the blocker on the manifest before resolving it, and republished the dashboard.
- Merged the rebased base and re-applied this branch inside the package (`50b8752e`): the
  imports, the pinned invocations, and `SKILL.md` keeping this branch's summaries step and
  table in #158's pinned form.
- Moved by hand what git had no counterpart to rename: `bastler/github_links.py` and
  `test/bastler_test/fixtures/promotion_summaries.json`.
- 692 tests pass in `test/bastler_test`; `scripts/format_docstrings.py` reports no change.
- Pushed; GitHub reports the pull request mergeable. Description, `plan.yaml` and `roadmap.md`
  updated; the blocker is cleared.

## Next

- Nothing on this session's account. The pull request is out of draft, which in this workflow
  is the developer's approval-for-promotion signal, so it is deliberately left that way.
- Still the item's own outstanding work, untouched by this resolve: whether an
  already-registered scheduled run's notification setting can be changed in place - the
  `Open` entry in `roadmap.md`.
- One review thread is unresolved on purpose: the shared dataclass-exception deferral, which
  is the developer's to close.
- `needs-resolution` clears itself on the next pass; nothing here removes it.

# #120 - sidebar-bug-fix-chips (workflow-unification)

## Plan

Resolve the base-merge conflict the 2026-08-12 maintenance pass reported, after
fork `main` was fast-forwarded from cram2 to `e123c383`.

## Done (2026-08-12, `299d1d53`)

- Merged `origin/main`. Two conflicts, both predicted on 2026-08-01 as the cost
  of landing behind #122:
  - `tests/test_build_dashboard.py` - additive on both sides except the
    example-locking assertion, which takes #122's now-correct two-entry
    `ready_to_review`; this branch's bug-chip example test re-appended after it.
  - `example/screenshots/dashboard-overview.png` - re-rendered from the merged
    example rather than taken from either side.
- Checked the merged tree keeps what `main` decided while away:
  `is_ready_for_dependent_review` survives the auto-merge, and the walkthrough
  prose carries both sides in order. 399 tests across the three CI directories.
- Left the other two screenshots alone, verified rather than assumed: the
  filtered sidebar hides the group that changed, and the action-buttons crop
  shows cards with no notes to collapse.
- Replied on the pass's conflict comment, refreshed the description (its
  `## Promote` link was destroyed by an intermediate edit and restored),
  recorded the round in `plan.yaml` + `roadmap.md` (`c52a870a`), commented on
  issue #102, republished the dashboard.

## Next

Nothing outstanding from this session. `needs-resolution` is deliberately left
for the next maintenance pass to clear itself. Not re-drafted - the user took
this pull request out of draft themselves, so this session's job on it ends here.

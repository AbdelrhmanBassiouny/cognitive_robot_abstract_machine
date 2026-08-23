**Session: `/plan-item-resolve rdr-refactor D-core-aid` (PR #63, branch `D-core-aid`).**
This session's own branch carries no commits - the resolution needed none.

Plan, as settled once the context was gathered:

1. Reply to and resolve the three review threads the 2026-08-22 round left open, after
   checking each ask against the branch head rather than the outdated diff snippet. **Done** -
   all seven threads on #63 are resolved, each with its own reply naming `c21e1fe3`.
2. Restore the `## Promote` section the description had lost while the `cram2-link-sent`
   label claimed it was there - the actual blocker, since that label stops any maintenance
   pass rebuilding the link and only clears at `in-review`/merged. **Done** - a plain compare
   link, because a prefilled one is neutralised into inline code when written from a session.
3. Record it: item `notes` + `session`, roadmap section 27, tracking issue #94, dashboard.
   **Done** except the dashboard, which needs `markdown`/`nh3` installed.

Outstanding, none of it this item's:

- **#63 is the developer's to promote.** It is green, clean, out of draft and now has a
  clickable link; nothing further is owed on it here.
- Two `.claude/stack` defects found on the way, both `workflow-unification`'s `stack-tooling`
  track: a session rewriting a description silently drops `## Promote` and the label makes
  that permanent, and `promotion_summary()` returns the leading markdown heading (`## What`
  on #63) instead of the first prose paragraph. Neither has an item yet.

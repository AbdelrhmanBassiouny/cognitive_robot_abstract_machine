PR #124: https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/124
(draft, based off main, subscribed to activity)

Single-PR task, contained entirely in this session - not tracked as a
multi-PR plan.

Plan: hide the long `item.notes` text on plan-dashboard chips
(`.claude/skills/plan-dashboard/templates/dashboard.html`) behind a
collapsed-by-default `<details>`/`<summary>` toggle, reusing the existing
`.roadmap-details` collapse pattern, so a dashboard with several
long-note items doesn't force endless scrolling to see the whole board.

Done:
- Wrapped the notes `<div>` in `item_card` (dashboard.html) in
  `<details class="notes-details"><summary>Notes</summary>...`.
- Added `.notes-details`/`.notes-details summary` CSS mirroring
  `.roadmap-details`, collapsed by default (no `open` attribute).
- Verified visually via a rendered dashboard.html Artifact built from the
  skill's example/ fixtures with an injected long note: collapses by
  default, arrow toggles ▸/▾ on click, cards with no notes show no
  summary line.
- Ran `pytest .claude/skills/plan-dashboard/tests/` - 194 passed, no
  regressions.
- Committed (authored as the user, not the session's git-config identity)
  and pushed to claude/dashboard-chip-collapse-g5uyj1.
- Opened draft PR #124 against main, subscribed to its activity.

Next:
- Watch for CI results and review activity via the webhook subscription
  (no scheduled polling per personal notes) and react when events arrive.
- Nothing else planned - single focused change, no follow-up scope known.

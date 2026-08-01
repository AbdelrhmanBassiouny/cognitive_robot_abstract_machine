PR #124: https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/124
(draft, based off main, subscribed to activity)

Tracked as `dashboard-chip-notes-collapse` in the `workflow-unification`
plan (`dashboards` track), per the user's explicit request - added after
implementation since the work started as a single-session task before
that was raised. Also subscribed to the plan's tracking issue #102.

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
- Added the `dashboard-chip-notes-collapse` item to
  `workflow-unification`'s plan.yaml/roadmap.md, saved via save-plan.sh,
  and republished its dashboard Artifact (same URL, no drift, new item
  correctly classified as ready-to-review).
- CI: `test_each_lib (coraplex) / test` failed on the head commit with a
  pytest-xdist worker crash (INTERNALERROR, unrelated to this diff, which
  only touches the Jinja2/CSS template). Replied on the PR explaining why
  it isn't being fixed here; not yet re-run/confirmed flaky vs.
  persistent - watch for it recurring.

Next:
- Watch for CI results and review activity via the webhook subscription
  (no scheduled polling per personal notes) and react when events arrive.
- If the coraplex failure recurs on a re-run, look into it further; if it
  clears, no action needed.
- Nothing else planned - single focused change, no further follow-up
  scope known.

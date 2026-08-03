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
- CI: `test_each_lib (semantic_digital_twin) / test` also failed - 2 real
  (non-flaky) assertion failures in test_multi_sim.py's mesh-material
  builder (materials sharing a texture get empty/duplicate names).
  Unrelated to this diff (no path from a plan-dashboard template to
  semantic_digital_twin's mesh adapter); matches this repo's established
  pattern of unrelated robotics CI noise on `.claude/`-only PRs. Replied
  on the PR; not fixing it here.
- Two `origin/main` merge commits landed on this branch from outside any
  session (2026-08-02/03, correctly authored as the user - likely an
  automated restack process). After the second merge: the earlier
  mesh-material failures are GONE (cleared by main's own
  texture-resolution fix, 2f459043 - confirms they were pre-existing/base
  issues, not this diff's). A new, different failure appeared instead:
  `test_each_lib (semantic_digital_twin) / test` - a pytest-xdist worker
  crash on test_bidirectional_synchronous_publish_does_not_stall (ROS
  sync test), same shape as the earlier coraplex worker crash, still no
  path back to this diff. Replied on the PR explaining both; not fixing
  either. `test_claude_dev_tooling` (the job that runs plan-dashboard's
  own suite) is green throughout.
- A third `origin/main` merge landed the same way (2026-08-03), bringing
  in a new Gazebo adapter (semantic_digital_twin/adapters/gazebo.py) and
  its tests. New failure: 6 errors in test_gazebo.py::TestSmallWarehouseWorld,
  all PathResolutionError - a missing ROS package
  (aws_robomaker_small_warehouse_world) in the CI image, an environment
  gap for the newly-merged feature, unrelated to this diff. The earlier
  worker-crash test passed this run. Replied on the PR; not fixing it
  here. Pattern is now well-established: every CI failure on this PR has
  come from unrelated upstream code arriving via external main-merges,
  never from this diff.

Next:
- Watch for CI results and review activity via the webhook subscription
  (no scheduled polling per personal notes) and react when events arrive.
- If the coraplex/semantic_digital_twin worker-crash flakes recur, look
  into it further; if they clear, no action needed.
- Nothing else planned - single focused change, no further follow-up
  scope known.

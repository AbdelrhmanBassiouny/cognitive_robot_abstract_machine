# claude/hidden-deferred-plan-items-6weef1 — draft PR #157

Hide deferred items on a plan dashboard by default, behind their own sidebar
checkbox, with indentation kept correct across all four visibility states.
Tracked as `deferred-items-hidden-by-default` in `workflow-unification`'s
`dashboards` track.

## Plan

1. Add the plan item to `workflow-unification` and push the manifest — done.
2. Replace the named done-hidden indent pair with one `StackPosition` per
   `VisibilityFilter`, driven by `HIDEABLE_STATUSES` — done.
3. Template: per-filter CSS, one checkbox per hideable status, wrap arrows
   looped rather than branched — done.
4. Tests first, then docs (`SKILL.md`, `example-walkthrough.md`) — done.
5. Open the draft PR, record the PR number, republish the dashboard, post the
   structural change to tracking issue #102 — done.

## Done

- `232 passed` in `.claude/skills/plan-dashboard/tests` (218 before).
- Verified in headless Chromium against the real `rdr-refactor` dashboard:
  all four toggle states checked for computed `display`, `margin-left` and
  which wrap arrow is visible.
- Committed as "Hide deferred items on a plan dashboard by default", pushed,
  draft PR #157 opened off `main`.
- `plan.yaml` + `roadmap.md` updated on `claude/personal-notes`; dashboard
  republished at the existing artifact URL; issue #102 commented.

## Next

Nothing outstanding in this session. CI had not reported when the PR was
opened. If the user asks for more work here: #111 touches the same template
(LOC/CI chips) and will conflict textually when it lands — resolution is to
keep both.

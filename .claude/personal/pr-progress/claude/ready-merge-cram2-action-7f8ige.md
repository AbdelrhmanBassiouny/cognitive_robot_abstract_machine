# claude/ready-merge-cram2-action-7f8ige — planning-only session (no PR)

**What this branch is for:** nothing is committed to it. This session was asked to design
the "ready to merge into cram2" dashboard sidebar + one-click upstream create-PR link, and
to fit it into the `workflow-unification` plan as a new item. Plan data must never live on
a tracked branch, so all output went to `claude/personal-notes` and the tracking issue.

**Done (2026-08-01):**
- Asked the four design questions that actually change the item's shape; user settled all four:
  depend on #111 and share `development_tooling`; body = fork PR description truncated + link;
  CI is a chip, never an exclusion; `in-review` is what removes an item from the list.
- Added item `ready-to-promote-upstream-links` to `workflow-unification` (`dashboards` track,
  wave `upstream`, `depends_on: [shared-pr-state-chips]`), plus a roadmap addendum recording
  the eligibility predicate, the URL format, the `upstream_repository` config decision, and
  why `stack.toml` was rejected as its home. Saved to personal-notes (`99385385`).
- Posted the structural change on tracking issue #102 (comment 5150988459).
- Republished the dashboard Artifact (19 items, no drift). Had to `force` — another session
  had published since; verified by WebFetch first that its version was the same generator's
  older output (18 items, pre-dating this edit), so nothing was lost.

**Next:** nothing on this branch. The item is `not_started` and cannot start until #111
leaves draft; implementation gets its own branch off `claude/shared-pr-state-chips` via
`/plan-item-kickoff workflow-unification ready-to-promote-upstream-links`.

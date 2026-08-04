# `plan-item-bootstrap` — added to `workflow-unification`

This session's job was to **add a plan item and decide its base**, not to
implement it. No branch or PR was opened; nothing was pushed to
`claude/plan-item-create-skill-axupew` (the plan data lives on the
personal-notes branch).

## The request

Make the first step after a plan is approved be: create the branch and a
draft PR, write the plan/branch/session into `plan.yaml` + `roadmap.md`,
mark the item `in_progress`, publish the dashboard — *then* implement.
Plus: base it on Python scripts and models, with the skill only saying when
to run them.

## Decisions taken

1. **Which skill** — asked the user, since "the plan item create skill" was
   ambiguous between `/add-plan-item` and `/plan-item-kickoff`. Answer:
   **both, via one shared script**. `plan-item-kickoff` step 5 is the
   primary caller; `add-plan-item`'s "new item" outcome gets a one-line
   reference. `/add-plan-item`-only was rejected on its own terms — that
   skill states it never creates a branch or pushes.
2. **Base: fork `main`, `depends_on: []`** — decided by running #135's own
   `check_scope_overlap.py`, not by feel. Only `.claude/skills/add-plan-item/`
   is absent from `main`, needed for exactly one line; by the
   prefer-the-change test that line goes on #135's branch while it is still
   an open draft. Everything else (`plan-item-kickoff/SKILL.md`,
   `save-plan.sh`, `plan_manifest_tools.py`, `.claude/hooks/tests/`) is on
   `main`.
3. **Tests in `.claude/hooks/tests/`**, which `ci.yml` already runs — no new
   pytest-directory constant, which sidesteps the single `ci.yml` line that
   #135, #106 and #107 all conflict on.
4. **Script at `.claude/hooks/plan_item_bootstrap.py`**, beside
   `plan_manifest_tools.py`, so it rides the `dev-tooling-save-plan-python`
   migration instead of needing a second move later.

## Done

- Manifest item + roadmap section saved (`6ed9a7d2`). Hit a stale-save race:
  the notes branch moved under me mid-edit (#139's live-run findings), so I
  re-fetched and re-applied — which also improved the PR-creation risk note,
  since those findings supersede the 2026-08-03 probe table.
- Commented the structural change on tracking issue #102.
- Dashboard republished to the same URL. 37 items, no drift, no
  auto-corrections; the new item is the only one listed "ready to start".

## Next (for whoever implements it)

- `/plan-item-kickoff workflow-unification plan-item-bootstrap`.
- Two things the script cannot do and must hand back explicitly: the
  dashboard republish (Artifact tool needs a live session) and creating the
  PR (`POST /repos/{o}/{r}/pulls` has never been in any probe table). Do not
  add a third copy of the gh-CLI-else-token rule.
- The master index at `/plan-dashboard` (no argument) was **not** refreshed —
  it republishes a separate page.

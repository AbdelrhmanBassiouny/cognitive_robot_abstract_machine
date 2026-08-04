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

## Done (round 2): the PR-creation question, settled by probe

`POST /pulls` with an unresolvable `head` returns **422** (`docs.github.com`),
not the proxy's **403** (`docs.anthropic.com`) — so the endpoint is authorised
and a script *can* create the PR. Identical across exported `GH_TOKEN`, junk
token and no header: within a session the credential is irrelevant, which
corrects the user's "given an exported token" framing on mechanism while
confirming the outcome. Untested: an actual creation, `draft: true`, and
attributed identity — a 422 on `head` stops evaluation first.

Item notes + roadmap updated (`197169ba`), issue #102 commented, plan
dashboard republished.

## Done (round 2): master index refreshed, and a stale URL cache fixed

Five of seven `dashboard-urls.yaml` entries plus `_index` pointed at deleted
artifacts. Repointed at the live ones (`3ddb6161`), verified two ways: exact
plan-title match, and the live index's own links. Index republished at
`094b785f`.

## Next

- `/plan-item-kickoff workflow-unification plan-item-bootstrap`.
- Only **one** hand-off remains for the script: the dashboard republish
  (Artifact tool needs a live session). Creation still goes through the one
  shared backend `dev-tooling-github-api-unification` builds — not a third
  copy of the gh-CLI-else-token rule — because the token *is* the credential
  outside this proxy.
- **For a human:** two workflow-unification dashboards exist. `07123af6` is
  current (37 items) and is what the cache uses; `36572776` is stale (36
  items) and now orphaned. Nothing was deleted.

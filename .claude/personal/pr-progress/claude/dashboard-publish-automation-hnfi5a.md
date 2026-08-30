# PR #218 - plan dashboards published as a Pages site from an Action

Tracked as `workflow-unification` / `stack-board-single-site` (PR 4).
Branch `claude/dashboard-publish-automation-hnfi5a`, off `main`, draft.

## Plan

Publish every plan's dashboard continuously, with no live session, since only
a session can call the Artifact tool and a published page was therefore only
as fresh as the last time someone ran `/plan-dashboard`.

1. `build_site.py` - headless entrypoint rendering all plans + the index. Done.
2. `personal_notes.py` / `github_api.py` - the notes-branch reads and the bulk
   pull request listing it needs. Done.
3. `.github/workflows/plan-dashboards.yml` - Pages deploy on pull request
   events, on renderer changes, and on `workflow_dispatch`. Done.
4. Tests + docs. Done: 34 new tests, 277 in the suite (was 243), 558 across
   the four directories CI runs (was 531).

## Decisions worth remembering

- **Off `main`, not stacked on #111**, at the user's explicit "I do not want to
  wait". A workflow's `pull_request` triggers fire from the base branch's copy
  of the file, so the feature is inert until it is on `main`; stacking on a
  branch conflict-blocked since 2026-08-29 would have shipped nothing.
- **One deliberate file overlap with #111**, which carries its own
  `build_site.py` at the same path. Same path, same CLI contract, so the merge
  is one file resolved in favour of #111's richer version; this branch's
  `github_api.py`/`personal_notes.py` are then deletable.
- `fetch-depth: 0` is load-bearing - the notes-branch worktree the
  merged-to-done correction pushes from cannot push out of a shallow clone.

## Next

Nothing outstanding on the branch. Awaiting review.

- Not carried by this PR and still open on the item: the
  every-fork-PR-belongs-to-a-plan invariant, the repo/branch/upstream
  repository variables, and the three inconsistent poll-interval statements.
- The first run after merge is the real proof: `configure-pages` has to enable
  Pages on this repository, which no test can exercise.

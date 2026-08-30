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
4. Tests + docs. Done: 52 new tests, 293 in the suite (was 243).

## Decisions worth remembering

- **Off `main`, not stacked on #111**, at the user's explicit "I do not want to
  wait". A workflow publishes for every plan only once it is on `main`: a copy on
  a stacked branch runs on that branch's own PR events and nothing else, and
  `workflow_dispatch` needs the file on the default branch at all. Stacking behind
  a branch conflict-blocked since 2026-08-29 would have shipped nothing.
  (I first wrote this as "`pull_request` triggers fire only from the base branch's
  copy" - wrong, and the first run refuted it by running from this branch.)
- **The `github-pages` environment only accepts deployments from the default
  branch**, so `actions/deploy-pages` can never run from a pull request. The first
  run failed on exactly that. The site goes to the `plan-dashboards-site` branch
  instead, with `pages_site.py` pointing Pages there; a test pins the rejected
  route out.
- **The checkout names no branch**, after two goes at naming one. It first said
  `github.event.repository.default_branch` meaning "main's scripts", which on this
  fork is the regenerated `integration` branch. Pinning it to `main` instead had
  the opposite fault: `main` carries no `build_site.py` at all, so every route but
  a merge to `main` would have checked out an empty tree. The workflow and the
  scripts land in one commit, so the run builds with the tree it started on -
  which is what `integration-refresh.yml` does, checked rather than assumed.
- **Which branch carries the file decides which triggers reach it**, and the
  three differ. `workflow_dispatch` is offered only from the default branch
  (`integration` here). A `pull_request` run uses that pull request's own merge
  ref, so it fires only for pull requests whose base already carries the file -
  `main`, for the fork's ordinary pull requests. `push` fires on the branch it
  names. So a copy on `integration` is dispatchable and a copy on `main` reacts
  to every pull request; neither substitutes for the other, and no workflow
  design changes that.
- **One deliberate file overlap with #111**, which carries its own
  `build_site.py` at the same path. Same path, same CLI contract, so the merge
  is one file resolved in favour of #111's richer version; this branch's
  `github_api.py`/`personal_notes.py`/`pages_site.py` are then deletable.
- `fetch-depth: 0` is load-bearing - neither the site branch's push nor the
  notes-branch worktree the merged-to-done correction pushes from works out of a
  shallow clone.

## Next

Nothing outstanding on the branch. 293 tests in the suite. Awaiting review, and
one deployment decision that is the user's.

The user does not want to merge this to `main`. What that costs, stated rather
than worked around: the `pull_request` trigger reaches only pull requests whose
base carries this file, so without `main` it covers this pull request alone.
Un-drafting #218 makes it eligible for the next integration rebuild, which puts
it on the default branch and makes `workflow_dispatch` available - a manual
refresh of all ten plans, which is the trigger they named. Closing the gap
between those two means either landing it on `main` later or adding a `schedule:`
cron like `integration-refresh.yml`'s; the cron was deliberately not added, since
it was not asked for and the standing no-scheduled-checks rule makes it their
call rather than mine.

- Living on `integration` has one fragility: that branch is regenerated from
  scratch, so a rebuild that drops this tip takes the workflow off the default
  branch and dispatch stops being offered until a later build carries it.
- Not carried by this PR and still open on the item: the
  every-fork-PR-belongs-to-a-plan invariant, the repo/branch/upstream
  repository variables, and the three inconsistent poll-interval statements.
- The first real run has to enable Pages on this repository and create the
  site branch, which no test can exercise.

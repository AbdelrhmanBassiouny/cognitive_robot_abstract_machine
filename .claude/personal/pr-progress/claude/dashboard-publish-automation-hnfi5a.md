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
4. Tests + docs. Done: 52 new tests, 295 in the suite (was 243).

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
- **The fork's default branch is `integration`, not `main`.** The checkout said
  `github.event.repository.default_branch` meaning "main's scripts"; that is 172
  commits of unlanded work carrying no `build_site.py`, so the job would have had
  no script to run. It names `SOURCE_BRANCH: main` explicitly now. Knock-on:
  `workflow_dispatch` only offers a workflow on the default branch, so dispatch
  works once an integration rebuild carries the file. `push`/`pull_request` are
  unaffected - both name their branch.
- **One deliberate file overlap with #111**, which carries its own
  `build_site.py` at the same path. Same path, same CLI contract, so the merge
  is one file resolved in favour of #111's richer version; this branch's
  `github_api.py`/`personal_notes.py`/`pages_site.py` are then deletable.
- `fetch-depth: 0` is load-bearing - neither the site branch's push nor the
  notes-branch worktree the merged-to-done correction pushes from works out of a
  shallow clone.

## Next

Nothing outstanding on the branch. Awaiting review.

- Not carried by this PR and still open on the item: the
  every-fork-PR-belongs-to-a-plan invariant, the repo/branch/upstream
  repository variables, and the three inconsistent poll-interval statements.
- The first real run has to enable Pages on this repository and create the
  site branch, which no test can exercise - that is what merging proves.

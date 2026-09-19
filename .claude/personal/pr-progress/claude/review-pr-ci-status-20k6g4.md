## Plan

Answer "what is the CI state of every in-review pull request, on the fork and
upstream, and is any red one already fixed elsewhere". The upstream half needed
a capability that did not exist, so this branch built it.

## Done

- Read the fork CI of all 17 `in-review` pull requests, twice (2026-09-19
  morning, then again after the 264 approval).
- #269's red robokudo check is the seeded-RANSAC flake that #405 fixes, and
  #269 touches only `krrood`. Recorded in #269's description; no code change.
- #264's CI was never run until Abdelrhman approved it; it now runs and is
  green so far.
- Built the upstream CI read into `upstream_reviews.py` (pull request #420,
  which Abdelrhman marked ready for review at 11:19Z - finished, no further
  commits).
- Dispatched it for all 17 branches from #420's own ref. Every branch has an
  upstream pull request (#641-#661) and every one is red; 15 fail exactly
  `test_each_lib (giskardpy)` and `test_each_lib (robokudo)`.
- Found the mechanism: `ci.yml` runs every job inside
  `ghcr.io/${GITHUB_REPOSITORY,,}:jazzy`, so the fork and cram2 each test in
  their *own* container image, rebuilt only when `.github/docker/` changes on
  that repository's main. `git ls-remote cram2 refs/pull/<n>/head` confirms the
  upstream pull requests carry the identical commits that pass on the fork, and
  the two repositories' `.github/` trees are identical - so the difference is
  the image, not the code. The fork last rebuilt its image on 2026-08-31.
- Ran the integration build with #420 in it (workflow_dispatch of
  integration-refresh.yml): build branch `integration-20260919-113141`, #420
  merged in cleanly, candidate pull request #421 opened for judging.

## Next

- Not doable from here: reading an upstream job log to name the actual error.
  api.github.com and github.com are both blocked for cram2 in a Claude session
  (403 "not enabled for this session"); `add_repo` read access is git-only. It
  needs a second reader that fetches the upstream job log from the fork's
  runner - new work, so a new branch, since #420 is finished.
- The integration build cannot publish while `claude/performatives-clean` (#14)
  stays conflicted against its base: that is what fails the candidate's "Run
  the maintenance pass" check (exit 10, BRANCH_NEEDS_ATTENTION).

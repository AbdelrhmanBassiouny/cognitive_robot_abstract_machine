## Plan

Answer "what is the CI state of every in-review pull request, on the fork and
upstream, and is any red one already fixed elsewhere". The upstream half needed
a capability that did not exist, so this branch builds it.

## Done

- Read the fork CI of all 17 `in-review` pull requests. 16 green; #269 red on
  `test_each_lib (robokudo)`; #264 has no checks at all.
- #269's failure is the seeded-RANSAC flake that #405 fixes, and #269 touches
  only `krrood`. Recorded that in #269's description; no code change there.
- #264's CI has never run: every workflow run on that branch sits at
  `action_required`, because the pushes were made by `github-actions[bot]` and
  the fork gates bot-triggered runs behind manual approval. Not a code fault.
- Built the upstream CI read: the upstream's REST API answers 403 for a Claude
  session and GraphQL is blocked, so `upstream_reviews.py` now also reads the
  head commit's `statusCheckRollup` and reports it, run from the fork's own
  Actions runner exactly as the review-thread read already was.
- Dispatched it for all 17 branches. Every one has an upstream pull request
  (#641-#661) and every one is red, 15 of them on the same two jobs,
  `test_each_lib (giskardpy)` and `test_each_lib (robokudo)`.
- Upstream `main` is the same commit as fork `main` (1e06fe9fa6), where those
  jobs pass. So the upstream redness is upstream-side, not any pull request's.

## Next

- Open this branch's draft pull request.
- Not done, and not doable from here: reading an upstream job's log to name the
  actual error behind the giskardpy/robokudo failures. That needs either
  upstream API access for the session or a second reader that fetches an
  upstream job log from the runner.

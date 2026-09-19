## Plan

Make an upstream check's *reason* readable from a session. #420 reads which
upstream checks are red; this branch reads the log behind each one, on the same
runner, for the same reason.

## Done

- `--failure-logs` / the `failure_logs` workflow input: reads each failed
  check's Actions job log through `gh` on the runner and quotes an excerpt.
- Excerpting has three named rules - pytest's `short test summary info` block,
  the runner's `##[error]` annotations, the log's last lines - so a job that
  died before pytest still says why. Timestamps come off; 40 lines is the cap.
- A check with no Actions job behind it (a commit status from another service)
  and a check still running are both skipped rather than read.
- `.claude/upstream_reviews/tests` was in no CI job at all. Added it to
  `test_claude_dev_tooling` through a resolved path.
- 62 tests pass in the suite (15 new); 561 in the CI tooling suite.
- Draft pull request #424, based on #420's branch.

## Next

- Verify the runner's `GITHUB_TOKEN` can actually read a cram2 job log. The
  dispatch is queued behind the integration candidate's matrix. If it answers
  403, the excerpting still stands but the read needs a credential that can see
  the upstream, and that is the thing to report rather than work around.
- Then: name the actual error behind `test_each_lib (giskardpy)` and
  `test_each_lib (robokudo)`, which are red on all 17 promoted branches while
  the identical commits pass on the fork.

## Note for later

`f6fb64e686` on #420's branch carries a `Co-Authored-By: Claude Opus 5
<noreply@anthropic.com>` trailer, which AGENTS.md forbids outright. #420 is
finished, so nothing was pushed to fix it - it needs a rewrite of that commit,
or a note to whoever merges it.

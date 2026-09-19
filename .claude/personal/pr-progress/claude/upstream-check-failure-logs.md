## Plan

Make an upstream check's *reason* readable from a session. #420 reads which
upstream checks are red; this branch reads the log behind each one, on the same
runner, for the same reason.

## Done

- `--failure-logs` / the `failure_logs` workflow input: reads each failed
  check's Actions job log through `gh` on the runner and quotes an excerpt.
- Three named excerpting rules - pytest's `short test summary info` block
  (stopping at the runner's error annotation), the `##[error]` annotations for
  a job that died before pytest, the log's last lines otherwise. Timestamps and
  the test runner's colour come off; 40 lines is the cap.
- `gh` needs `--allow-escape-sequences` or it returns the log and then refuses
  to write it, because pytest colours its own output.
- A check with no Actions job behind it, and a check still running, are both
  skipped rather than read.
- `.claude/upstream_reviews/tests` was in no CI job at all. Added it to
  `test_claude_dev_tooling` through a resolved path.
- 64 tests pass in the suite (17 new); 561 in the CI tooling suite.
- Draft pull request #424, based on #420's branch.

## Verified, and what it found

The runner's own `GITHUB_TOKEN` *can* read a cram2 job log - that was the open
question and the answer is yes. Dispatched against #652 it named both failures:

- robokudo: `test_query.py::TestQueryInterface::test_query - assert True is
  False`. Not the seeded-RANSAC flake at all, so #405/#652 was never going to
  clear it.
- giskardpy: four in `test_integration_daisy.py` - `TestJointGoals::test_joints1`
  and `test_joints2` off at 2-decimal tolerance, and two
  `TestCollisionAvoidanceGoals` self-collisions violated by ~2mm.

The same commit runs the same 821 tests on the fork and passes all of them,
both libraries. Same code, same workflow, same test set, different verdict - and
the one known difference is the container image, `ghcr.io/${GITHUB_REPOSITORY,,}:jazzy`,
which is per repository and rebuilt only when `.github/docker/` changes on that
repository's main. Numeric drift at 2 decimals and 2mm collision margins is what
a differently built solver stack looks like.

## Next

- Nothing outstanding on this branch. The upstream fix is `update_docker` on
  cram2, which needs upstream access.

## Note for later

`f6fb64e686` on #420's branch carries a `Co-Authored-By: Claude Opus 5
<noreply@anthropic.com>` trailer, which AGENTS.md forbids outright. #420 is
finished, so nothing was pushed to fix it - it needs a rewrite of that commit,
or a note to whoever merges it.

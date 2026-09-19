## Status

Finished. Abdelrhman marked #424 ready for review at 12:28:50Z, after leaving
one review comment and before asking for it to be handled. Left ready, not
re-drafted, no further work started on it.

## What it does

Reads the log behind each failed upstream check on the fork's own runner, and
quotes an excerpt under the checks section. Three named rules: pytest's
`short test summary info` block (stopping at the runner's error annotation),
the `##[error]` annotations for a job that died before pytest, the log's last
lines otherwise. Timestamps and the test runner's colour come off; 40 lines is
the cap. Behind `--failure-logs` / the `failure_logs` workflow input.

## The review round

`ALLOW_ESCAPE_SEQUENCES` was a bare module constant between two classes.
Moved onto `GitHubCommandLineClient` as a `ClassVar[str]` beside `executable` -
the shape `Author.UNKNOWN_LOGIN` uses in the same file, and what
`maintenance_git_commands.py` does in keeping a command's arguments with its
runner. Not folded into `GitHubEndpoint`: a flag is not an endpoint.

Found while moving it: the `gh` stub recognised only `api graphql --input -`
and exits 64 on anything else, so `read_job_log` had no transport coverage at
all. The stub now matches the endpoint call *and the flag*, so dropping the
flag fails loudly - checked by removing it and watching three tests go red.
67 tests in the suite. Replied on the thread and resolved it.

## What it found, on the way

The runner's `GITHUB_TOKEN` can read a cram2 job log - that was the open
question. Dispatched against #652:

- robokudo: `test_query.py::TestQueryInterface::test_query - assert True is
  False`. Not the seeded-RANSAC flake, so #405/#652 was never going to clear it.
- giskardpy: four in `test_integration_daisy.py` - two joint goals off at
  2-decimal tolerance, two self-collisions violated by ~2mm.

The same commit runs the same 821 tests on the fork and passes all of them.
Same code, same workflow, same test set - the difference is the container
image, `ghcr.io/${GITHUB_REPOSITORY,,}:jazzy`, per repository and rebuilt only
when `.github/docker/` changes on that repository's main. The fix is
`update_docker` on cram2, which needs upstream access.

## Left for Abdelrhman

- The integration build cannot publish: `Run the maintenance pass` fails
  because `claude/performatives-clean` (#14) is conflicted, and
  `PIPELINE_WORKFLOWS` excludes only the two integration workflows, so that
  repo-wide check counts as a verdict on the build's tree.
- Candidate #421 also breaks `test_each_lib (krrood)`: #192 renames
  `Match.matches_with_variables` to `_matches_with_variables_`, #65 carries
  tests calling the old public name. Both 23/23 green alone.
- Fixed on request: `f6fb64e686` on #420's branch carried a `Co-Authored-By:
  Claude Opus 5 <noreply@anthropic.com>` trailer, which AGENTS.md forbids.
  Amended to `c5eaefeb50` (message only, identical tree, author and dates kept),
  and this branch replayed onto it as `74f0b9fa91..42843342b1` - also identical
  trees, so #424's diff is unchanged. Both force-pushed with lease.
- krrood pair triaged: #192's `_..._` convention is the intended interface, so
  #64 is the half that adapts. The eight sites are listed on #64; the change
  cannot land until one of cram2 #658 / #662 merges, because `main` still has
  the old names. `integration-conflict` deliberately left on #192 - withholding
  it costs one branch, withholding #64 costs thirteen.

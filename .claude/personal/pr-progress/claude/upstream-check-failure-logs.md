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

The same commit runs the same 821 tests on the fork and passes all of them:
fork CI on `1e06fe9fa6` - byte-identical to cram2's main - was green on
2026-09-18T14:44Z. Same code, same `ubuntu-latest`, same workflow, so the
per-repository container image `ghcr.io/${GITHUB_REPOSITORY,,}:jazzy` is the
remaining variable.

Corrected on Abdelrhman's challenge: the image is *not* stale on cram2 - it is
stale on the fork. The fork's last `update_docker` was 2026-08-31T21:43Z (16
runs, none since), and its image blob is dated 2026-08-31T21:47Z on a
`ros:jazzy` base layer from 2026-08-17. Tigul rebuilt cram2's yesterday by
`workflow_dispatch`, which leaves no git trace - `.github/docker/` has not
changed since f879be4f6c on 2026-08-31, which is why inferring staleness from
the push-path trigger was wrong. So the green result is the *old* image and
the red one is the *new* image. Do not run `update_docker` on cram2 as a fix:
it rebuilds from the same unpinned inputs.

Nothing in the build is pinned. `FROM ros:jazzy` is a moving tag, already
moved from the fork's 2026-08-17 base to 2026-09-16. apt and the
`pip install poetry objgraph treon jupytext jupyterquiz jupyter-book
pytest-xdist uv` line carry no versions. `setup_workspace.py` clones 17
external repositories with `git clone -b <branch> --single-branch` and no
commit pin, so each rebuild takes whatever those branches point at - among
them `Universal_Robots_ROS2_Description@jazzy` and
`iai_weiss_wpg_300-120-gripper@main` (Daisy is the UR + Weiss gripper) and
`robokudo_msgs@ros2_jazzy`. A moved robot description is the natural reading
of joint goals off at 2 decimals and self-collisions violated by ~2mm, and of
a robokudo query interface flipping to `assert True is False`.

Unverified, because cram2's API and its GHCR package both refuse this session
(403 / 401): the exact rebuild time versus the failing run I read. If the run
predates the rebuild the direction above could still flip. `ci.yml` has a
`workflow_run` trigger on `update_docker` completion, so the rebuild will have
re-run CI on cram2's main - that run's colour settles it, and Abdelrhman can
see it.

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

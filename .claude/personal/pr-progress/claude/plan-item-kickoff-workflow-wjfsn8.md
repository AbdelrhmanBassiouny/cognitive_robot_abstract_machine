# integration-branch-ci-verdict — PR #191 (draft)

Plan `workflow-unification`, track `stack-tooling`. Branch
`claude/plan-item-kickoff-workflow-wjfsn8`, based on
`claude/plan-item-kickoff-workflow-ixbvxl` (#154's head).
Kickoff session: https://claude.ai/code/session_01Aw5p5xzSFUKNCueN8oG6Tg

## The plan

Move `integration.py`'s verdict off the local `integration_test_command` run and onto
GitHub CI, give `integration` a stable half, and add a pytest marker with a job that runs
only what it marks.

Settled at kickoff:
- `integration` is a **pointer** force-updated to the candidate on green; the candidate PR
  is closed, not merged.
- The verdict is the **marked job's conclusion**, not the whole matrix run.
- The marker is **not** excluded from the default pytest run.

Where the code goes: Actions/check-run reads, `POST /pulls` and the reference force-update
extend `maintenance_github.py`'s existing `GitHubRepository`; the candidate/verdict half is
a new `integration_verdict.py`; the targeted job is a new
`.github/workflows/integration-checks.yml` (`pull_request` + `workflow_dispatch`);
`pytest.ini` registers `integration_conflict`.

Deletions: `integration_test_command`, `ConfigurationKey.INTEGRATION_TEST_COMMAND`,
`--test`/`--no-test`, `TestCommandNotConfiguredError`, `_run_tests`,
`BuildCommand._test_command`, `FailureLocation.test_command`/`_suite_passes`.

## Done

- Branch opened off #154's head, bootstrap commit pushed, draft PR #191 opened.
- Manifest: `branch`, `session`, `pull_request_number`, `status: in_progress` recorded;
  roadmap section appended; dashboard republished.

## Next, tests first

1. Marker registered in `pytest.ini`, with a test that `-m integration_conflict` selects
   only marked tests.
2. Actions/check-run client on `maintenance_github.py`, against a stubbed transport.
3. `integration_verdict.py` — publish a candidate, read a conclusion back, advance the
   stable branch only on green. These tests are also the `ReportKey` wire-format guard
   #154 deferred here.
4. `integration-checks.yml` + a test parsing its triggers and marker filter.
5. Rewire `build` / `locate-failure` / `block-branch`; delete the local-run surface.
6. Automatic clearing of `integration-conflict` from the branch the marker names.
7. Triage SKILL.md, stack README, PR description.

## Carried

- #154 is `dirty` against `main` and carries `needs-resolution`; this branch inherits that
  until #154 takes its base merge. Not ours to fix.
- Crosses #185's bastler move (`.claude/stack/` → `bastler/`) and #158's pin. Whichever is
  still open when the other lands merges `main` and re-applies inside the package.
- The marked job runs with tooling dependencies only — a reproduction test inside a
  robotics package needing the docker matrix would not be collectible there.

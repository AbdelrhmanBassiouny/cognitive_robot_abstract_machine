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

## Review round of 2026-08-23, applied in 5da2d55213

Two threads, both answered and resolved. 622 tests pass.

`GitCommandRunner.common_directory` replaces the inline `rev-parse --git-common-dir` in
`provenance_path`, and resolves the answer itself rather than returning git's relative
form. Resolving at the call site is what produced the provenance defect fixed the commit
before, so putting it inside the method makes that mistake unrepresentable rather than
fixed once. Mutation-checked: `answered.resolve()` fails only the provenance test.

Both replay tests opened by describing the defect instead of the behaviour under test.
Each now leads with what it pins. Swept both rather than the one commented on - the
module's pre-existing tests already state why the behaviour is right and only then the
mechanism, so this is the file's own convention rather than a new one.

Also applied black to `integration.py`. The disagreement is pre-existing on the base at
`FailureLocation.find` - confirmed by stashing this branch's change and re-checking - but
committing that file puts it through the format hook anyway, so it was taken deliberately
rather than left for the hook to do silently. Worth knowing: the locally-installed black
was 26.5.1 while `.pre-commit-config.yaml` pins 25.11.0, and 26.x wants a *different*
reformat of the same lines (the parenthesized `with` form). Install the pinned versions
before trusting a formatter check.

## The #158 collision, recommendation posted

`pin-tooling` copies only `.claude/stack/`, which is right against main and wrong once
#154's chain is in the tree: #151's `.claude/shared/` extraction means all three entry
points carry `sys.path.insert(0, Path(__file__).parent.parent / "shared")`, which from a
pinned copy resolves to a directory that does not exist. Reproduced by copying
`.claude/stack/*` into an empty directory - `stack.py`, `maintenance.py` and
`integration.py` all die with `ModuleNotFoundError`, so it is the whole pass rather than
one command.

#158's own `test_the_pinned_copy_carries_what_the_maintenance_executor_imports` already
pins the real tooling and runs `maintenance.py --help` from the copy, so it is the
reproduction and needs no change - it simply cannot fail until the two branches meet.

Recommended: pin `.claude/shared/` alongside, preserving the relative layout, with both
directories in the digest. Rejected resolving `shared/` back to the checkout (reinstates
the swap hazard the branch removes) and waiting for #185 (the real cure, but a draft, so
excluded from every build while #158 and #154 are carried today). Nothing pushed to #158.

## Still open

- **#191 is a draft**, so it is excluded from every build. Until it is un-drafted the
  workflows it will carry cannot reach `integration`, whatever else is resolved.
- **`integration` is at 899a04a and was never verified green** - that build reports
  `tests_passed: null`. Advancing it needs the #158 fix and #154's base merge.
- Part D itself - the CI verdict, `integration_verdict.py`, the marker, the workflows -
  is not started. Both commits so far are build-reliability fixes underneath it.


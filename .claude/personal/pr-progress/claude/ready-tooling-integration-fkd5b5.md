## Tooling label from the changed files - PR #284 (ready)

**Branch** `claude/ready-tooling-integration-fkd5b5`, based on
`claude/integration-priority-labels` (#281).

**This session's work** resolving the conflict with the base and checking the
red CI. One merge commit `f9de13ed29`, pushed.

The base had picked up #185's move of the tooling out of `.claude/stack/` into
the `bastler` package, so the whole directory was renamed underneath this
branch. Resolved:
1. `changed_paths.py` and `maintenance_tooling_label.py` moved into `bastler/`,
   `test_tooling_label.py` into `test/bastler_test/`, all on `bastler.` imports.
2. Test reaches the root through `bastler.package_layout.REPOSITORY_ROOT`
   instead of `Path(__file__).parents[3]`, and `test_maintenance` through a
   relative import.
3. Two textual conflicts, both import blocks only
   (`maintenance_commands.py`, `maintenance_report.py`).
4. `tooling-label.yml` installs the package and runs
   `python -m "${MAINTENANCE_MODULE}" label-tooling`; `STACK_DIRECTORY` now
   names only the README's directory.
5. `stack.toml`'s `tooling_paths` comment no longer calls `bastler/` a place an
   in-flight branch is moving the tooling to.
6. `scripts/format_docstrings.py` run over every touched file.

**Test state** `pytest test/bastler_test --confcutdir=test/bastler_test`:
930 passed, 5 failed. Base branch alone: 912 passed, the *same* 5 failed. All
five start a subprocess with an interpreter that has no `bastler` installed,
which CI does install. So the merge adds 18 passing tests and no failures.

**CI** the one red check, `Integration refresh`, is fork-wide and not this
PR's: every run of that workflow has failed for days, on `#291`, `#293` and on
the scheduled runs of `integration`. It checks out the *default branch* on a
`pull_request` event but runs the *PR's* workflow file, so its
`integration.py block-branch` call hits a main that has no such subcommand -
exit 2, `USAGE`. Belongs to whoever owns `integration-refresh.yml`, not here.
A push does not re-trigger it (it fires on schedule / dispatch /
`ready_for_review` only).

**Left alone deliberately**
- The `needs-resolution` label: a maintenance pass owns setting and clearing it.
- Draft state: #284 is ready-for-review and was most likely marked so by hand,
  so it was not flipped back.
- `integration_test_command` in `bastler/stack.toml` still names
  `.claude/stack/tests`, which #185's move deleted. Pre-existing on the base,
  not this PR's to widen into.

**Knock-on** #293 is based on this branch and will need the same package move
applied to `integration_tooling.py` and its test once this lands.

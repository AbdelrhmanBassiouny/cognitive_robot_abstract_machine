# PR progress: claude/montessori-results-recording-jnrgfy (#262)

Plan item `run-results-recorded-into-sql` of `icra-experiments`, track
`long-term-memory`, tracking issue #252. Execution mode: auto.

## Plan

Cut the recording half of #256 (`montessori_monitor_and_recording`) off `main`,
taking exactly this file list and nothing else:

- `experiments/src/experiments/montessori/__init__.py` (empty, load-bearing)
- `experiments/src/experiments/montessori/results_database.py`
- `experiments/src/experiments/montessori/results_recording.py`
- `experiments/src/experiments/montessori/sorting_results.py`
- `test/experiments_test/test_montessori_results_database.py`
- `test/experiments_test/test_montessori_results_recording.py`
- `test/experiments_test/test_montessori_sorting_results.py`
- `test/experiments_test/conftest.py` - only the `montessori_results_session` fixture
- `cognitive_robot_abstract_machine/orm_interfaces.py` - `experiments` declares
  `("coraplex", "segmind")`
- `experiments/scripts/generate_orm.py` - imports `segmind.orm.ormatic_interface`
- `experiments/pyproject.toml` - declares `segmind`

Then rewrite every docstring reference to something that does not exist on `main`,
regenerate the ORM interfaces, and run the three new test modules plus
`test/version_test/test_dependency_declarations.py`.

## Decisions taken

- **Dangling references are wider than the item named.** Besides
  `franka_montessori_demo`, `insertion_experience` and `run_montessori_demo.sh`,
  `DEFAULT_DATABASE_URI` cites `coraplex_panda_demo/demo3.py` (absent from `main`)
  and both `suggest_correction()` methods cite
  `experiments/src/experiments/montessori/README.md` (absent from every branch).
  The README citations are user-facing failure text, so they are repointed at
  `semantic_digital_twin/scripts/create_postgres_database_and_user_if_not_exists.sql`,
  which exists on `main`.
- **The database is named for the board, not the robot.** The first cut left
  `franka_montessori_sorting_results` alone; the developer overrode that in review on
  2026-09-05, so `199c478ac` renames it to `montessori_sorting_results` and
  `FRANKA_MONTESSORI_SORTING_DATABASE_URI` to `MONTESSORI_SORTING_DATABASE_URI`.
  Neutral rather than Tracy-specific, since both demos record here - flagged on both
  threads and left open rather than resolved, because that is not the literal ask.
- **No second `Footprint` rename.** #223 already renames the perception `Footprint` to
  `RectifiedFootprint`; the hazard is recorded in #262's description instead.

## Done

- Setup: installed the plan-dashboard dependencies (`markdown`, `nh3`).
- Branch cut off `origin/main`, pushed, draft PR #262 opened.
- Manifest: `branch`, `session`, `pull_request_number`, `status: in_progress`
  recorded; roadmap section appended, then a second section on what the session
  container could and could not verify. Dashboard republished.
- All eleven files added/edited and committed (`bd618b94d`), pushed. The three
  test modules are byte-identical to #256's; only the three source modules
  differ, and only in their docstrings and the two `suggest_correction()`
  strings.
- PR description updated to match, including the verification section below.

## Review round 1 (2026-09-05)

Two threads, both on naming, both from the developer: r3941124169 on
`DEFAULT_DATABASE_URI` and r3941124727 on `DATABASE_URI_ENVIRONMENT_VARIABLE`.

- Renamed in `199c478ac`, pushed. Both threads answered with the reasoning for
  the neutral name and **left open** - the ask was "change it for the tracy
  demo" and a robot-neutral name is not literally that, so it is the
  developer's to close.
- PR description rewritten: the paragraph claiming the name was left alone is
  replaced by a section explaining the rename and the #256 consequence.
- The branch had also been fast-forwarded past `main` by a merge someone else
  pushed (`0c58f50e4`); the rename sits on top of it.

## Verified

- `test/version_test/test_dependency_declarations.py`: 20 passed. Also checked
  red - removing the `segmind` line fails
  `test_imported_workspace_members_are_declared[experiments]`.
- `test/cognitive_robot_abstract_machine_test/`: 61 passed, covering the
  `("coraplex", "segmind")` declaration and generation order.
- The `__init__.py` claim, demonstrated: `pkgutil.walk_packages` over
  `experiments` yields the three montessori modules with the file, nothing
  without it.
- `scripts/format_docstrings.py` run on every modified source file.

## Not verifiable in this container

`scripts/regenerate_all_orm.py` and the three new test modules need ROS: the
generator dies on giskardpy's `DebugExpressionPublisher`,
`segmind.datastructures.events` imports `geometry_msgs`, and the
`experiments_test` conftest imports `rclpy`. The regeneration fails identically
on unmodified `main` here, so it is the environment, not the change. CI runs
both inside the ROS image.

## Next

Two review threads are open by choice, waiting on the developer to accept the
neutral name or ask for the Tracy one. Otherwise waiting on CI in the ROS image
to run the three test modules and the ORM regeneration. Per the notes, this
session does not watch the PR.

## Outstanding

- Subscribing to tracking issue #252 was denied by the auto-mode permission
  classifier, so this session is not watching it.
- The artifact wake subscription for the dashboard could not be registered
  (the artifact service refuses them from this session), so a republish
  elsewhere will not reach here.

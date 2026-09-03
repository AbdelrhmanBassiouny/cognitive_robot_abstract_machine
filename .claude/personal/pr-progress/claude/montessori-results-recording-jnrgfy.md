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
- **`franka_montessori_sorting_results` is not renamed.** It is a value, three tests
  assert it appears in failure messages, and renaming it would point this branch at a
  different database from the demo branch recording to the same one.
- **No second `Footprint` rename.** #223 already renames the perception `Footprint` to
  `RectifiedFootprint`; the hazard is recorded in #262's description instead.

## Done

- Setup: installed the plan-dashboard dependencies (`markdown`, `nh3`).
- Branch cut off `origin/main`, pushed, draft PR #262 opened.
- Manifest: `branch`, `session`, `pull_request_number`, `status: in_progress`
  recorded; roadmap section appended.

## Next

1. Add the three test modules and the conftest fixture first (TDD), red.
2. Add the four modules with rewritten docstrings, and the four declarations.
3. `scripts/regenerate_all_orm.py`, then run the four test modules.
4. Commit, push, keep the PR a draft, republish the dashboard.

## Outstanding

- Subscribing to tracking issue #252 was denied by the auto-mode permission
  classifier, so this session is not watching it.

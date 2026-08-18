# montessori_perform_queried_action (plan item of montessori-eql-stack, track action-execution)

## Branch

`claude/queried-action-perform-button-vg2vz3`, not the manifest's original
`montessori_perform_queried_action` - the harness forbids pushing anywhere else.
The manifest now records the real name (as montessori_replay_event_annotations
already does for its own session branch). Based on `montessori_event_replay`
(#165), restacked onto its post-main-merge tip b76c8ede8.

## Status: implemented, pushed (2dee8f57), draft PR #176 open

Seven layers, all done, each with tests:

- [x] `cramera/knowledge/performable_action.py` - `PerformableAction`
- [x] query_runner - `CarriesAPerformableAction`, `AnswerRow.perform`,
      `RenderResult.perform` beside the rows
- [x] `cramera/live/action_execution.py` - `LiveActionExecution` + state + its two
      exceptions
- [x] bridge - register/relay/`perform_action`, `perform` on `/info`
- [x] http - `GET /perform`, `POST /perform {action}`
- [x] web - `core/perform.js`, perform column + status line in the EQL panel,
      `perform:state` emitted from the scene panel's existing 3 s `/info` poll
- [x] montessori demo - `PerformableInsertion`, `SortingActionExecution`, the
      between-shapes checkpoint, the live-only "what can the robot insert?" preset
- [x] `cramera/README.md` section

## Test state

- cramera suite: 566 green (was 545 on the base).
- experiments: the suite cannot run outside the CI container here (no rclpy, empty
  ORM interfaces, uninitialised `cramera/scenes` submodule). Ran the new/affected
  files with `--noconftest`: 42 pass, and the one failure
  (`TestDeclaredBundlePresets`) reproduces on the untouched base - it is the
  missing submodule.
- A local venv for running any of this had to be built by hand at
  `<scratchpad>/venv` (python3.12 + editable workspace installs + mujoco,
  giskardpy_bullet_bindings, objgraph, pyflakes, black, docformatter).

## Next

Nothing outstanding. Draft PR #176 is open against `montessori_event_replay`; no
`bug` label, this is a feature. Per the personal notes this session does not watch
it - re-draft after any further push, and report red CI in chat rather than acting
on it unprompted.

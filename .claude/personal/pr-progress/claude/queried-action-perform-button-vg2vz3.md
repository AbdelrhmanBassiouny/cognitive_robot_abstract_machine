## Next
Nothing outstanding. Draft PR #176 is open against `montessori_event_replay`; no
`bug` label, this is a feature. Per the personal notes this session does not watch
it - re-draft after any further push, and report red CI in chat rather than acting
on it unprompted.

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

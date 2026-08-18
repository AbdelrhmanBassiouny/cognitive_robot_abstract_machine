# montessori_perform_queried_action (plan item of montessori-eql-stack, track action-execution)

## Branch

Session's designated branch is `claude/queried-action-perform-button-vg2vz3`, not the
manifest's `montessori_perform_queried_action`. The harness forbids pushing anywhere
else, so the manifest gets updated to the real name (unlike #175, which kept its
manifest name). Based on `montessori_event_replay` (#165), the item's declared
dependency.

## Plan

Mirror the replay button #165 gives queried segmind events, one layer at a time:

1. cramera/knowledge/performable_action.py - `PerformableAction`, the parallel-list
   entry an answer row carries (same shape as `ReplayWindow`).
2. query_runner - `CarriesAPerformableAction` protocol; `AnswerRow.perform`;
   `RenderResult.perform` beside the rows.
3. cramera/live/action_execution.py - `LiveActionExecution` abstraction + its state,
   mirroring `LiveRunControl`.
4. bridge - register/relay, `perform_action`, status announcement.
5. http - `GET /perform` (state) and `POST /perform {action}`.
6. web - `core/perform.js` (pure), EQL panel column + status line, index.html.
7. montessori demo - a `PerformableInsertion` domain, `SortingActionExecution`, and the
   sorting loop honouring requests at its existing checkpoints.

Tests alongside each layer (pytest + node), TDD.

## Status

- [ ] not started yet - just laid the plan out

## Next

Implement layer 1-2 with tests.

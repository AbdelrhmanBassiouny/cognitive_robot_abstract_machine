# Live-state EQL queries for the stretch demo (branch `stretch_live_state_queries`)

Base: `luca/stretch_cramera` (Luca's fork). PR head will be pushed to `origin`
(AbdelrhmanBassiouny fork), base `LucaKro:stretch_cramera`. Draft.

## Goal
Preset buttons in cramera's EQL panel that answer questions about the *running*
demo: what the robot holds right now, its current goal, its current action.
Ported from the Montessori EQL stack (#164-#170) but stripped to the minimum:
no autocomplete/suggestions, no verbalization, no viewer highlighting, no voice,
no replay, no query scopes, no database evaluation.

## Session
https://claude.ai/code/session_b564e821-c7e7-4e47-bc00-aab3886fdbc7

## Decisions taken with the user
- Wire `start_visualization`/`attach_plan` into the stretch demo in this PR.
- "current goal" = outermost running action; "current action" = innermost.
- The live query source is generic, lives in cramera, auto-registered by
  `LiveVisualization.start()` - no coraplex change, no per-demo registration.

## Plan
1. `knowledge/query_domain.py` - QueryDomain (ported).
2. `knowledge/query_runner.py` - RenderResult/RowRenderer moved out of
   eql_session.py + EqlQueryRunner over declared domains.
3. `knowledge/eql_session.py` - declares the recorded scene's domains, delegates.
4. `live/query.py` - LiveQuerySource ABC + NoQuerySourceRegistered.
5. `live/robot_state.py` - RobotAction/HeldObject entities read off the bridge.
6. `live/bridge.py` - register_query_source/query_presets/run_query.
7. `live/http.py` - GET /presets, POST /eql.
8. `live/visualization.py` - register the robot-state source on start.
9. Frontend: core/query_source.js, panels/eql/panel.js, index.html.
10. Stretch demo wiring.
11. Tests (pytest + node js tests), README.

## Status
Just started - branch created, nothing committed yet.

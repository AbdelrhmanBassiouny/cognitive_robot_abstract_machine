# Live-state EQL queries for the stretch demo

Branch `stretch_live_state_queries` -> draft PR
https://github.com/LucaKro/cognitive_robot_abstract_machine/pull/3
(base: `LucaKro:stretch_cramera`, head pushed to `origin`).
Session: https://claude.ai/code/session_b564e821-c7e7-4e47-bc00-aab3886fdbc7

## Goal
Preset buttons in cramera's EQL panel answering questions about the *running*
demo: what the robot holds, its current action, its current goal. Ported from
the Montessori EQL stack (#164-#170) minus autocomplete, verbalization,
highlighting, replay, voice, scopes and the results database.

## Decisions taken with the user
- Wire `start_visualization`/`attach_plan` into the stretch demo (it had none).
- "current goal" = outermost running action; "current action" = innermost.
  A parent whose child runs is reported running too, so in the stretch demo's
  flat plan those two coincide - that is the truth, not a bug.
- The query source is generic, lives in cramera, registered by
  `LiveVisualization.start()`. No coraplex change, no per-demo registration.

## Shipped
- `knowledge/query_domain.py`, `knowledge/query_runner.py` (RenderResult and
  RowRenderer moved out of eql_session.py + EqlQueryRunner over domains);
  `eql_session.py` now only declares the recorded scene's domains.
- `live/query.py` (LiveQuerySource ABC), `live/held_objects.py` (HeldObject,
  read in `Bridge.bind`), `live/robot_state.py` (RobotAction +
  RobotStateQuerySource + the presets).
- Bridge: query source registration, `plan_nodes`, `object_bodies`,
  `get_held_objects`, `query_lock`. HTTP: `GET /presets`, `POST /eql`.
- Frontend: `web/core/query-source.js` + EQL panel routing, with fallback to
  the recorded scene when the demo offers nothing.
- Tests: `test/cramera_test/test_live_query.py` (38), `js/test_query_source.js`
  (5). Full cramera suite 610 green. Smoke-run against a real Stretch world.

## Outstanding / next steps
- PR is a draft, unreviewed; CI on LucaKro's fork not checked.
- coraplex/experiments suites could not run locally (no rclpy/ROS here); CI
  runs the stretch demo script (`examples_and_demos.yml`), which now starts the
  cramera bridge, as the bullet-world demo already does.
- Not ported (deliberately, ask before adding): suggestions/autocomplete,
  verbalization read-back, answer highlighting in the renderer, event replay,
  voice questions, query scopes / episodic memory.

# EQL where-is queries + general viewer highlighting (montessori)

Branch is based on `origin/montessori_fast_inline_monitor` (per request), not main.

Plan:
1. cramera query runner: `highlightable_ids` set on EqlQueryRunner/RowRenderer —
   any string answer value naming a published viewer object gets highlighted
   (general, not query-tied; unknown values are ignored client-side anyway).
2. cramera live bridge: demos can register extra fixed scene entities (board
   Body, hole Regions) so the viewer renders + highlights them;
   body_geometry learns Region (`area`) measurement/mesh serving;
   run_query passes published keys as highlightable ids.
3. experiments/montessori: scene_layout.py records (HoleRecord, BoardRecord,
   InsertionGoalRecord + SceneLayout.of_world); new `hole`/`board`/`goal`
   domains + where-is presets (square hole, all holes, montessori box, goal
   per shape); ShapeUnderTest.related_highlight_ids -> its published shape
   body; _attach_cramera registers board+holes and builds the layout.
   New presets stay OUT of MONTESSORI_PRESETS (bundle presets.json submodule
   pin is unfetchable, sync test must keep passing).
4. Tests in test/cramera_test + test/experiments_test; format; push.

Status: DONE and pushed (commits 354b8760 cramera, 72cf8f75 montessori).
All four plan points implemented with tests. Test results: cramera suite 437
passed; new + touched experiments tests 70 passed. Environment-only failures
(also fail on base, not caused by this change): the presets.json bundle-sync
test (cram-scenes submodule pin 2438a52 unfetchable from public repo) and two
ROS-dependent tests under the local rclpy mock shim (pass in CI with real
ROS). Frontend needed no change: latest query already replaces highlights,
unknown ids ignored.
PR: draft #164 (montessori_eql_where_is_highlighting -> montessori_fast_inline_monitor),
same commits as claude/montessori-eql-highlighting-bptp3r. This session's job
on it is done per the opening-a-PR-ends-obligation rule.
Outstanding: not verified in a live end-to-end demo run (needs ROS + Postgres);
bundle presets.json untouched (submodule pin unfetchable), new presets live-only.

# Demo recording + event replay popup (stacked on montessori_eql_where_is_highlighting)

Second PR, stacked on `montessori_eql_where_is_highlighting` per request.
Branch: montessori_event_replay (same commits as claude/montessori-eql-highlighting-bptp3r HEAD).

Plan:
1. cramera knowledge: ReplayWindow (fixed LEAD/TAIL 5 s shifts around a moment);
   RowRenderer marks entity rows carrying a datetime `timestamp`
   (CarriesATimestamp protocol) and set_of rows containing datetime values with
   `__replay__` {start, end}; datetimes render as readable times.
2. cramera live: DemoRecording (rolling, 20 Hz cap, 600 s retention,
   thread-safe) fed from Bridge.snapshot(); cleared on world replacement;
   Bridge.replay_clip; GET /replay?start&end endpoint.
3. frontend: core/replay.js (pure: ?replay= parsing, popup URL incl. live=,
   frame stepping with 1 s loop hold, clip label); answer table strips
   __replay__ into row.replay; EQL panel adds "▶ replay" buttons (live only)
   opening a popup (named window 'cramera-replay'); config.js mounts only the
   scene panel under ?replay=; robot_scene panel replay mode (geometry attach
   as live, loops /replay clip, no live poll, no /move posts, no run controls,
   blue REPLAY badge).
4. montessori: event domain already queryable; tests pin event rows carrying
   ReplayWindow.around(detection timestamp) incl. the "what was detected, and
   when?" preset. No experiments src change needed.

Status: DONE, pushed, PR opened (draft #165, montessori_event_replay ->
montessori_eql_where_is_highlighting, commits ddfbefa7 cramera + 79081cf0
montessori tests). Cramera suite 459
passed; experiments failure set byte-identical to base (30 env-only
failures: Postgres, py_trees/ROS shim gaps, submodule presets.json); node JS
tests incl. new test_replay.js pass. Session's job on the PR is done per the
opening-a-PR-ends-obligation rule.
Outstanding: not verified in a live end-to-end demo run (needs ROS +
Postgres); replay shifts fixed at 5 s lead/tail (easy to change in
ReplayWindow).

Follow-up on #165 (user request): scenes submodule pin fixed in ef46d536 —
old pin 2438a523 was orphaned (never pushed to public cram2/cram-scenes; no
commit there ever had a Franka_Montessori bundle), new pin = scenes main
2230683. Bundle presets-sync test now skips while the checked-out submodule
has no Franka_Montessori bundle (CI-safety rule), re-arms once one is
published. PR #165 description updated; suites re-run green (cramera 459,
live-query file 20 passed + 1 skipped). Open follow-up: publish the
montessori bundle (incl. new presets) to cram-scenes.

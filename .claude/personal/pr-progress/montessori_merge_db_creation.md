## Live EQL queries for the Franka Montessori demo in the cramera UI

Goal: the cramera EQL panel's preset buttons, for the Franka_Montessori scene,
become questions answered by the *running* demo. Three questions drive the set:
was this shape inserted, where was it being inserted, why could it not be.

No PR opened yet — all work is local on `montessori_merge_db_creation`.

### Done (all TDD: failing test first, then code)

1. `EqlQueryRunner` extracted from `EqlSession` (cramera/knowledge/query_runner.py,
   query_domain.py). `RowRenderer` gained declared `entity_types` + `Pose` rendering
   (`body_geometry.pose_label`). `PythonClass` now owns its related highlight ids.
2. Live query endpoint on the bridge: `cramera/live/query.py` (`LiveQuerySource`,
   `NoQuerySourceRegistered`), `Bridge.register_query_source/run_query/query_presets`
   behind a lock, `BridgeStatus.query`, `GET /presets` + `POST /eql` on port 8765.
3. Panel routing: `web/core/query_source.js` decides live vs recorded; panel listens
   to `live:changed`. Scene bundles may declare `presets.json`, which replaces the
   generated scene presets and renders greyed out until a demo attaches.
4. `ShapeSortingBoard.has_fallen_through(shape, world)` and `insertion_target_for(...)`
   extracted from `InsertMontessoriShapeAction` (which now delegates), so the ground
   truth and the aim point are readable without a live action.
5. `insertion_diagnosis.py`: ranked reason — informative `PlanFailure`, else
   `NOT_PICKED_UP` / `DROPPED_BEFORE_INSERTION` / `WEDGED_IN_HOLE` /
   `RELEASED_OFF_TARGET` / `UNDIAGNOSED`. Needed `ContactDetector` +
   `LossOfContactDetector` added to `build_shape_monitor` — no gripper contact was
   being tracked at all before, so a drop left no evidence.
6. `sorting_progress.py` (thread-safe live record) + `live_query_source.py`
   (17 presets, mirrored into `cramera/scenes/Franka_Montessori/presets.json`,
   with a test keeping them in step).
7. Demo wired: `--cramera`, `SortingProgress` threaded through `_insert_all_shapes`,
   and `_insert_shape_or_none` now returns the exception it used to discard.
   READMEs updated in cramera and experiments/montessori.

### State

- cramera: 355/355 pass.
- experiments montessori modules: 95 pass, 1 pre-existing failure
  (`test_montessori_event_monitoring.py::test_shape_falling_through_...`,
  `MissingReferenceFrameError` in the test's own `move_to`) — confirmed failing
  with my changes stashed.
- `test_franka_panda_equipment.py` fails to import (`PANDA_SCENE_BODIES_TO_DISCARD`
  missing) — also pre-existing, untouched file.

### Also done

8. `run_montessori_demo.sh` at the repo root beside `run_cramera.sh`: starts the
   cramera server, waits for its port, opens the viewer (no `?scene=`, so it
   auto-attaches to the demo), then runs the demo with `--cramera` in the
   foreground; a trap tears the server down. Covered by
   `test_run_montessori_demo_script.py`, which pins the ports against
   `cramera.server.DEFAULT_PORT` / `cramera.live.http.DEFAULT_PORT` and checks
   every flag its help advertises against `_parse_arguments`.
   Verified end to end: real MuJoCo run, bridge answered all 17 presets mid-sort,
   shape fell through, exit 0, both ports released.

### Next

- `cramera/scenes` is a submodule: `Franka_Montessori/presets.json` needs its own
  commit in `cram2/cram-scenes`.
- Not done, deliberately: persisting the diagnosis (`ShapeInsertionAttempt` gains no
  fields; would need `scripts/regenerate_all_orm.py` + a migration). Live-only was
  the chosen scope.
- Flagged, not fixed: `target_horizontal_offset` is persisted and documented but
  `_action_plan` never reads it, so every attempt aims at the hole centre.
### Round 2 — object naming, run control, verbalization (all TDD)

9.  `MontessoriShape.shape_key` / `.object_name` (semantics.py). The world names every
    loose shape after its hole (`square_hole_shape`), so `ShapeUnderTest.name` read as
    the hole. `name` is now `cube` / `cylinder_1`, with `shape_key` its own field on
    `ShapeUnderTest`. `PlanStep.of_plan` / `SegmindEventRecord.of_event` take the
    tracked `ShapeUnderTest` instead of loose primitives; a never-begun shape now
    raises `UntrackedShapeError` rather than silently inventing a hole.
10. `cramera/knowledge/query_verbalization.py`: `QueryVerbalization.of_expression`
    builds one krrood fragment and renders it plain + HTML (`EscapedHtmlFormatter`
    escapes literals). `RenderResult.verbalization` carries it; the EQL panel renders
    it in `.qverb` above the rows. An `UnverbalizableExpressionError` costs the
    sentence, never the answer.
11. `cramera/live/run_control.py`: `RunCommand`, `RunActivity`, `RunControlState`,
    `LiveRunControl`, `NoRunControlRegistered`, `UnknownRunCommand`. Bridge gains
    `register_run_control` / `run_control_state` / `run_control_payload` /
    `apply_run_command` behind `_run_control_lock`; `BridgeStatus.control` carries the
    state so the existing 3 s `/info` poll drives the UI. `GET /run`, `POST /run`.
12. `experiments/montessori/run_control.py`: `SortingRunControl` over one
    `threading.Condition`. Pause freezes the `MujocoSim` physics thread *and* holds the
    sorting thread at its next checkpoint; restart is honoured at the next attempt
    boundary (and resumes a paused run so it can unwind); loop keeps rebuilding.
    `PausableSimulation` Protocol keeps it testable without MuJoCo.
13. Demo: `_insert_all_shapes` takes the control and checks it before each shape and
    each attempt; an abandoned run returns early and is *not* persisted.
    `_build_world_and_sort(node, arguments, iteration, control)` hands the new
    `MujocoSim` to `begin_iteration`. `main`'s `for` loop became a `while` that honours
    loop/restart; the old `while True: sleep` idle is now
    `control.wait_for_another_iteration()` (blocks forever with nothing registered,
    matching the previous behaviour).
14. `web/core/run_control.js` (12 node tests) + Pause/Restart/Loop in the scene panel's
    `.wf-btns`, rebuilt only when the button signature changes.
15. `run_montessori_demo.sh` now supplies `--world2 --viewer` unless the caller chose
    either way; `--viewer`/`--world2` became `BooleanOptionalAction` so `--no-viewer` /
    `--no-world2` exist. The demo module's own defaults are unchanged, so
    `batch_runner` / `headless_realtime_pacing_runner` are unaffected.

### State (round 2)

- cramera: 389/389 pass. montessori-related experiments files: 155/161.
- The 6 failures are all pre-existing, verified on a pristine `HEAD` worktree:
  `test_montessori_event_monitoring.py::test_shape_falling_through_...` and five in
  `test_montessori_insert_shape_action.py` (`EmptyUnderspecified: Plan failed`).
  `test_franka_panda_equipment.py` still fails to import (`PANDA_SCENE_BODIES_TO_DISCARD`).
- Note: those five insert-shape-action tests passed earlier in this branch's history and
  now fail at HEAD — worth a look, unrelated to this work.

### Round 3 — episodic memory, preset groups, two viewer bugs (all TDD)

16. **Loose objects (bug: picked shapes frozen in the viewer).** `Bridge.bind()` only
    published bodies *named like mesh files*, so the montessori world published none —
    the viewer was showing the recorded bundle's static shapes forever. Extracted
    `cramera/loose_objects.py` (`LooseObjects.keyed_bodies/mesh_named_bodies/
    free_floating_bodies/key_of`), which the onboarder's duplicate `free_floating_bodies`
    now delegates to, so recorder and bridge key objects identically. Also
    `body_geometry.mesh_file_of` + `Bridge._servable_mesh_path`, so a procedurally built
    object is served from its own `Mesh.filename` (and `format` comes from that path, not
    from the key). Verified: all 5 montessori shapes publish with the exact keys the
    bundle uses.
17. **Rebind on a rebuilt world (bug: restart leaves the viewer dead).** `_observe_tick`
    attached only `if bridge.world is None`, and `runner.start()` returned early when
    already serving — so after Restart the bridge kept snapshotting the abandoned world.
    Now `attach()` is called whenever the executing world differs, `_forget_previous_world`
    drops the dead plan/chart, and `start(world=...)` rebinds. The existing hook test
    encoded the bug and was rewritten. Frontend half: `core/live_attach.js`
    (`shouldAttach`) replaces the `autoAttachedLive` latch, so a viewer that lost the
    bridge re-attaches; only an explicit click off sticks.
18. **Answer table.** `core/answer_table.js` (`AnswerTable.of`) settles columns and
    classifies each value (`name`/`number`/`true`/`false`/`empty`/`text`); the panel
    renders a real `<table>` with a sticky header, zebra rows and per-kind colour, and
    `RowRenderer._column_names` drops the type prefix from headings (`ShapeUnderTest.name`
    → `name`) unless that would merge two columns.
19. **Query scopes.** `cramera/knowledge/queryable_knowledge.py`: `QueryScope`
    (`CURRENT_STATE`/`EPISODIC_MEMORY`, `.label`, `of_name`), `UnknownQueryScope`,
    `QueryEvaluation`/`InMemoryEvaluation`, `QueryableKnowledge(scope, domains,
    evaluation, extra_names)`. `LiveQuerySource.domains()` → `knowledge()`;
    `Preset.scope`; `Bridge.run_query(code, scope)` + `query_scopes()`;
    `GET /presets` gains `scopes`, `POST /eql` takes `scope`.
    `core/preset_groups.js` groups the buttons under headings (single group → no heading,
    so every other scene is unchanged).
20. **Episodic memory.** `cramera/knowledge/database_evaluation.py` translates via
    `eql_to_sql` and materializes rows inside the session.
    `results_database.ResultsDatabase` owns engine + schema creation (memoized per
    instance — `create_all` over the generated schema takes ~50 s, unaffordable per
    query); `_open_results_session` delegates to it. `MontessoriLiveQuerySource` gains
    `results_database` and `EPISODIC_MEMORY_PRESETS`; `extra_names` supplies `sum` (EQL
    leaves it out, it shadows the builtin) and `InsertionOutcome`.
    `test_montessori_episodic_memory.py` seeds a real sqlite results database and asserts
    the exact success-rate rows — no credentials, so it runs in CI.

### Deviations from what was asked (round 3)

- The user's snippet used `sum(comparator)` and `mode(...)`. krrood's `Sum` rejects a
  `Comparator` (needs a `Selectable`) — rewritten as
  `sum(case_when(outcome == FELL_THROUGH, 1, 0))`. `mode` has **no** SQL translation in
  `eql_to_sql` and no portable SQL aggregate behind it, so the "most likely failure"
  column was dropped and a *how did each shape's runs end?* preset added instead, whose
  per-outcome counts answer the same question.
- Column headings for aggregates read `Sum`/`Count`: `set_of` takes no aliases.

### State (round 3)

- cramera: 422/422 pass.
- Postgres: the user ran the provisioning command;
  `franka_montessori_sorting_results` on the local 5432 cluster now holds iteration 1
  (all five shapes `fell_through`), recorded with
  `headless_realtime_pacing_runner --world2 --no-rviz --iterations 1
  --exit-after-sorting`. All three episodic presets verified against it through a real
  `Bridge`.
- The success-rate preset gets no verbalization sentence: krrood has no grammar rule for
  `Sum(CaseWhen(...))`, so `QueryVerbalization.of_expression` returns None. Documented
  degradation — the answer is unaffected. The other two presets do word themselves.
- Killed two hung full-suite pytest runs left over from the previous session
  (~1.9 GB RSS each, 6.5 h old).

### Round 4 — the demo's segfault (root-caused from a core dump, fixed TDD)

21. **SIGSEGV during a `--cramera` run.** Diagnosed from the apport core dump kept at
    `/var/crash/_usr_bin_python3.12.1000.crash` (17:49 run; the 19:21 crash was dropped
    because apport keeps only one file per executable). Faulting thread is the **main**
    thread inside `casadi::SXElem::is_constant()`; `si_code=1` (SEGV_MAPERR) at
    `0x76216ae158e5`, nowhere near `$sp` — a wild pointer, not stack overflow.
    `_casadi.so` imports `PyEval_SaveThread`/`PyEval_RestoreThread`, so casadi **releases
    the GIL**, and its `SXNode` reference counts are non-atomic: two Python threads
    reading poses corrupt the graph and free a node still in use.
22. **The racer my work added**: `SortingProgress` stored live `Pose` objects
    (`ShapeUnderTest.target_pose`, `InsertionAttemptRecord.target_pose`), and
    `RowRenderer._jsonable` called `pose_label(...)` → `to_position_quaternion_list()`
    → casadi *on the HTTP thread*, while the main thread planned in casadi. This
    violated the rule stated in `cramera/live/hooks.py` and in the plan ("the HTTP
    thread only ever reads finished plain-Python records").
23. **Fix**: `cramera.body_geometry.NumericPose` (frozen; `position`/`quaternion` tuples
    of plain floats, `of_pose()`, `.label`). `pose_label` now delegates to it, so the
    wording is unchanged. `SortingProgress` reads poses out at record time, on the
    thread owning the world. `RowRenderer` renders a `NumericPose` as a value rather
    than an entity row (added to the three isinstance checks).
24. Tests: 3 in `test_body_geometry.py`, 3 in `test_montessori_sorting_progress.py`
    (`TestNothingSymbolicIsHandedOut`, including an invariant test that no recorded
    field is a `Point3`/`Pose`). All were failing first.

### State (round 4)

- cramera: 425/425 pass. montessori experiments: 201 passed, 7 failed — the same 7
  pre-existing failures already verified on a pristine HEAD worktree in round 2/3.
- `snapshot()` is only ever called on the plan thread, so the bridge itself was clean;
  the leak was only `target_pose`.
- Flagged, not fixed: `MujocoSimulator.add_entity` wraps a model recompile in
  `self.pause()` / `self.unpause()` (mujoco_simulator.py:1731). A viewer Pause landing
  inside that window is silently discarded when `add_entity` unpauses. Real bug in the
  run-control feature, but it lives in shared `physics_simulators` code and is not what
  crashed.
- Not proven: that the physics/synchronizer thread never evaluates casadi. Evidence
  points away from it (both segfaults were `--cramera` runs; the headless recording run
  finished clean), but it was not ruled out by reading.
- To capture a future crash, `/var/crash/_usr_bin_python3.12.1000.crash` must be removed
  first — apport will not overwrite it. Left in place for the user to decide.

### Round 5 — the segfault again, and the racer round 4 missed

25. **Round 4's fix was in the crashed run and did not save it.** The demo segfaulted
    again at 19:51. Files edited 19:39–19:45; the crashed process was born 19:48:33
    (`stat --time=birth` on its `/tmp/semantic_digital_twin_meshes_293115_*`). So
    `NumericPose` removed a real racer but not the decisive one. No fresh core: apport
    still held the 17:49 file and silently drops newer crashes.
26. **Re-read the 17:49 core across all 137 threads** (round 4 only inspected the
    faulting one). Exactly one thread in casadi (main, `SXElem::is_constant`), and
    **thread 22 running Python bytecode** — `np.array(...)` via `PyArray_Pack` /
    `PyArray_AssignFromCache_Recursive`. Legal only because casadi had released the GIL:
    two live consumers, which is the use-after-free.
27. **`Body.global_pose` builds a casadi object on every call.**
    `ForwardKinematicsManager.compute` (forward_kinematics.py:160) computes numpy and
    wraps it in a `HomogeneousTransformationMatrix`. So *any* thread reading a pose is a
    casadi thread — not just one doing visibly symbolic work. This is what made round 4's
    "only the HTTP thread touches casadi" reasoning wrong.
28. **The dominant racer is the TF publisher, on the physics thread.** `MultiSim._sim_to_world`
    (multi_sim.py:3324) says in its own docstring that it runs on the physics thread after
    every `mj_step`, throttled to `sync_rate_hz`; the demo sets `SYNC_RATE_HZ = 100`. It
    calls `world.notify_state_change()`, which fires `TFPublisher.on_state_change()` →
    `compiled_tf.evaluate()` — casadi, at 100 Hz, off the plan thread. Created unless
    `--no-rviz`. The one clean run on record (`headless_realtime_pacing_runner --world2
    --no-rviz`) is exactly the one that had no TF publisher; both segfaults had one.
29. **Fix taken (TDD):** `run_montessori_demo.sh` now defaults to `--world2 --viewer
    --no-rviz`, and the demo's flag became `--rviz/--no-rviz` (`BooleanOptionalAction`,
    default True) so the launcher's default is still overridable. The script's
    drop-if-the-caller-decided loop learned to negate a negative default
    (`--no-rviz` ↔ `--rviz`). Demo module defaults unchanged, so `batch_runner` /
    `headless_realtime_pacing_runner` are unaffected; `batch_runner`'s own `--no-rviz`
    is its own parser's flag and still forwards fine.
30. Tests: `test_it_turns_off_rviz_publishing` (new, failed first), plus
    `chosen_demo_defaults()` / `opposite_flag()` helpers. Two existing tests in
    `TestItChoosesTheDemosDefaults` were generalized rather than weakened: one pinned the
    defaults as an exact literal, the other assumed every default is a positive flag.

### State (round 5)

- `test_run_montessori_demo_script.py`: 16/16 pass.
- `/var/crash/_usr_bin_python3.12.1000.crash` deleted (user's call), so the next crash
  will actually be captured.

### Not done, and why (round 5)

- **The segmind monitor still reads the world off-thread.** `MontessoriEventMonitor`
  (event_monitoring.py:200) runs a `segmind-event-monitor` daemon thread whose detectors
  call `obj.global_pose` and do contact queries at 5 Hz. Real racer, 20× rarer than the TF
  publisher. The user approved ticking it on the plan thread, but there is no clean seam:
  `giskardpy.Executor` has no per-tick observer, so the options are monkey-patching
  `Executor.tick` (as `cramera/live/hooks.py` does) or a decorating `Pacer` injected
  through `GiskardExecutable._build_pacer` (coraplex/plans/executables.py:343) — whose
  configuration today is class-level attributes, i.e. globals. Both change shared code and
  need a design decision; ticking only at explicit demo points would miss the whole motion,
  which is when pick-up and insertion happen.
- **`TFPublisher` itself is unfixed**, only avoided. Evaluating a compiled casadi
  expression from a state-change callback is unsafe for any threaded simulation, not just
  this demo; it lives in `semantic_digital_twin` shared code.

### Round 6 — the racer caught in the act, and the monitor moved onto the plan thread

31. **Crashed again with `--no-rviz`** (confirmed in the fresh core's `ProcCmdline`), so
    the TF publisher was not the whole story. This time apport had a free slot and
    captured it: `/var/crash/_usr_bin_python3.12.1000.crash`, 20:14.
32. **Two threads in casadi, caught mid-race.** Thread 1 (main/plan) in
    `casadi::SXElem::is_constant()` with the GIL released; **thread 32 in
    `_wrap_delete_SX` → `SwigPyObject_dealloc`**, blocked in `PyEval_RestoreThread` —
    i.e. *destroying* an SX, dropping `SXNode` references, while the main thread
    dereferenced them. `si_code=1` (SEGV_MAPERR) at `0x75f50f5c1486`, far from `$sp`.
    Thread 67 was the cramera HTTP loop idle in `poll(timeout=500)`, so round 4's
    `NumericPose` fix is holding. Thread 22 was mujoco in `mj_step`.
33. **Round 5 under-rated the monitor badly.** `EpisodeSegmenterExecutor` subclasses
    giskardpy's `Executor`, so the monitor thread was running `Executor.tick()` — full
    motion-statechart tick plus `collision_manager.compute_collisions()` — not a light
    5 Hz pose sampler. It was a peer of the planner.
34. **And round 4's "snapshot() is only ever called on the plan thread" was wrong.**
    `cramera/live/hooks.py:166` patches `Executor.tick`, and the segmind executor *is* an
    `Executor`, so every monitor tick also ran `bridge.observe_tick()` →
    `apply_moves()` + `snapshot()` → `rounded_pose()` over every body → forward
    kinematics → casadi, **on the monitor thread**. This is why every segfault was a
    `--cramera` run, and why this one landed immediately after a viewer drag: the queued
    move was applied on the monitor thread.
35. **Fix (TDD):** `ControlCycleTicking` in `event_monitoring.py` ticks the monitor from
    `Executor.tick` (via `cramera.monkey_patch.MethodPatch`), so detectors read the world
    on the thread running the motion. `MontessoriEventMonitor` lost `_thread` /
    `_stop_requested` / `_run`; `start()`/`stop()` now drive/stop the ticking, and
    `tick()` stays public. A reentrancy flag stops the monitor's own executor tick from
    ticking it again — that also covers any future nesting, without importing segmind
    types for the guard. Ticks are wall-clock rate-limited to `tick_rate_hz` (5 Hz),
    because control cycles run at 50 Hz and a detector tick costs ~0.2 s.
36. The settle window executes no motion, so `_insert_shape` ticks the monitor directly
    per settle sample; `monitor` is threaded through `_insert_shape_or_none`.
37. Tests: `TestTheMonitorIsTickedOnTheThreadThatPlans` (6, all failed first) with
    `RunsControlCycles` / `TicksItRecords` mimics and an injected `MethodPatch`, so no
    compiled statechart is needed. `test_franka_montessori_demo.py`'s `_insert_shape`
    stub gained the new parameter — assertions untouched.

### Ordering note (round 6)

`MethodPatch` restores whatever it found at install time, so patches must unwind LIFO.
cramera installs its tick hook once at startup and never removes it; the monitor installs
and removes per shape on top of it. That holds today — but a second long-lived patcher of
`Executor.tick` would break it.

### Still open (round 6)

- **Not yet verified against a real run.** The suite passes, but only a long
  `./run_montessori_demo.sh` session proves the segfault is gone.
- The demo will be somewhat slower in wall-clock: ~0.2 s of detector work every 0.2 s now
  runs on the plan thread instead of alongside it. The total work is unchanged.
- cramera's tick hook now fires twice per control cycle whenever a monitor tick happens
  (once for the motion executor, once for the nested segmind one). Harmless, but it does
  double the snapshot work at 5 Hz.
- `TFPublisher` still unfixed (see round 5).

### Round 7 — the cost of serializing the monitor

38. **Measured, not guessed:** one detector tick is **99 ms** (median over 10, warm) for a
    single tracked shape. The module docstring's "around 0.2s" was pessimistic, but a
    control cycle is 20 ms, so a tick is still five control periods.
39. **Bug in round 6's rate limiter:** `_last_tick_time` was stamped *before* the tick, so
    the rate was start-to-start. With a 99 ms tick and a 200 ms interval the monitor ran
    99 ms of every 200 ms — half the plan thread, back-to-back. Now stamped after the
    tick, so the rate is the *gap*. `_last_tick_time` became `Optional[float]` (None =
    never ticked = due now), and a `clock` field was added so the tests drive time
    instead of sleeping.
40. **Rate lowered to 2 Hz** (`DEFAULT_TICK_RATE_HZ`), the user's choice from a costed
    menu: ~17% of the plan thread and ~17 ticks per 10 s insertion, against 33% and ~33
    at 5 Hz. Risk accepted: brief finger contact / loss-of-contact transitions are the
    samples most likely to be missed, and those are what `insertion_diagnosis` reads to
    tell `DROPPED_BEFORE_INSERTION` from `NOT_PICKED_UP`.
41. Tests: `TestTicksAreSpacedByTheGapBetweenThem` (2, failed first) with
    `AdvancesOnlyWhenTold` / `TicksOnAClockItControls` mimics.

### Where the 99 ms goes (profiled, for whoever does the broad phase)

Per tick, roughly: `ShapeCollection.as_bounding_box_collection_at_origin` ~50 ms (24
calls), `KinematicStructureEntity.has_collision` ~31 ms (158 calls),
`World.bodies_with_collision` ~24 ms, and ~1,545 casadi `DM` constructions. No single
knob — this is the broad-phase optimization the module docstring already records as not
yet done. Making it cheap is what would let the monitor tick often *and* fast.

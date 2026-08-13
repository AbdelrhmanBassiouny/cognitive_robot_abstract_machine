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
- Postgres provisioning is blocked on the user: no passwordless sudo, and the
  `semantic_digital_twin` role fails password auth on the local 5432 cluster (the 5433
  cluster their snippet points at is down). Command handed to them in chat.
- Killed two hung full-suite pytest runs left over from the previous session
  (~1.9 GB RSS each, 6.5 h old).

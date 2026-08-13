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

### Next

- `cramera/scenes` is a submodule: `Franka_Montessori/presets.json` needs its own
  commit in `cram2/cram-scenes`.
- Not done, deliberately: persisting the diagnosis (`ShapeInsertionAttempt` gains no
  fields; would need `scripts/regenerate_all_orm.py` + a migration). Live-only was
  the chosen scope.
- Flagged, not fixed: `target_horizontal_offset` is persisted and documented but
  `_action_plan` never reads it, so every attempt aims at the hole centre.

## Making the inline-ticking monitor cheap enough not to stutter

Fourth branch of this line of work. `montessori_merge_db_creation.md` records rounds
1-8, `stutter_montessori.md` round 9, `montessori_thread_safe_reads.md` rounds 10-12.
This branch is based on `stutter_montessori` -- the configuration that ticks the monitor
inline on the planning thread and so never had the segfault, only the stutter.

The bet: `montessori_thread_safe_reads` made a tick cheap in order to make it safe off
the planning thread. The same work makes the stutter go away when the tick stays *on*
that thread, and keeps the configuration that has never crashed.

### Round 13 -- the port

68. Cherry-picked all five of `montessori_thread_safe_reads`'s commits onto
    `stutter_montessori`. One conflict, in `event_monitoring.py`: `start()` spawns no
    thread here, so `_read_geometry_out` stays but as a warm-up (it keeps the one-time
    origin reads out of the first tick, which would otherwise stall a motion) rather
    than as a thread-safety measure. Dropped the `MUJOCO_LOG.TXT` that had been
    committed by accident.
69. Measured the same harness (`scratchpad/segmind_tick_timing.py`, 20 ticks) on both
    branches: **486.5 ms median on `stutter_montessori`, 73.1 ms after the port.** Note
    the branch's own docstrings claimed 99 ms; that number does not reproduce and was
    measured some other way. Worth telling the developer.

### Round 14 -- three more speedups

70. **`Bounds` answers for itself** (`geometry.py`): `from_points`, `empty`, `overlaps`,
    `contains`. Plus `NumericTransform.transform_points`,
    `KinematicStructureEntity.numeric_global_bounds` and
    `BoundingBoxCollection.enclosing_bounds`. `Bounds.empty` is what absent geometry
    reads back as, so no call site needs a special case.
71. **`InsideOf.compute_containment_ratio`** copied both meshes, transformed them, built
    a trimesh box around one and checked it was watertight -- to count vertices against
    six numbers. Now numpy. 73.1 -> 39.7 ms.
72. **`Shape.surface_area`** stated analytically instead of `shape.mesh.area`.
    `has_collision` was meshing every primitive in the world six times a tick; a
    cylinder's area is now 2*pi*r*(r+h) rather than its 16-gon's, ~3% larger.
    39.7 -> 25.6 ms.
73. **Bounds rejection before the exact relation** in `is_supported_by` (product-algebra
    intersection) and `is_body_in_region` (exact trimesh boolean). A rejected pair
    scored False/0.0 before too. 25.6 -> **12.5 ms**.
74. Total: **486.5 -> 12.5 ms, 39x.** A tick was 24 control periods at 50 Hz; it is now
    under one.
75. Raised `DEFAULT_TICK_RATE_HZ` from 2.0 back to 5.0 -- the value it had before the
    tick's cost forced it down. At 5 Hz the monitor takes a twentieth of the planning
    thread rather than half of it. Updated the docstrings and `--no-event-monitor` help
    that quoted 99 ms and said the switch was what made a watched run move smoothly.

### What is verified

- `scratchpad/segmind_monitor_casadi_trace.py`: still zero symbolic constructions off
  the main thread.
- sdt geometry/spatial-types/worlds suites: 386 passed, no new failures.
- Montessori monitoring/demo/script tests: 43 passed, 1 pre-existing failure
  (`test_shape_falling_through_its_hole_is_detected_as_pick_up_and_insertion`, confirmed
  failing on `stutter_montessori` too).
- segmind: the same 12 pre-existing `test_detectors` failures, no new ones.

### Known-unrelated failures in this environment

- `generate_orm.py` fails standalone with `Table '_MockedConvexSetDAO' is already
  defined`, which breaks collection of `test_world.py` and `test_gcs_polygons.py`.
  Worked around with `PYTEST_XDIST_WORKER=gw0`. **Worth the developer's attention.**
- The demo run the developer pasted died of `psycopg.errors.InsufficientPrivilege:
  permission denied for table ColorDAO` -- a database provisioning problem, not a code
  one -- and then segfaulted while unwinding from it. Not yet investigated.

### Next

- Head-to-head soak against `stutter_montessori` at equal wall clock would put a number
  on the end-to-end gain; only this branch has been soaked so far.
- `RotationMatrix.rotational_error` reports some rotations the long way round; latent
  bug, ask the developer.
- Still untouched: `TFPublisher` evaluating compiled CasADi from the physics thread, and
  `MujocoSimulator.add_entity` swallowing a viewer Pause (mujoco_simulator.py:1731).
- `body.global_pose` remains unsafe off-thread; callers wanting numbers should use
  `numeric_global_pose` / `numeric_global_transform`.
- No PR opened yet.


## Making the Montessori demo's detector thread CasADi-free

Third branch of this line of work. `montessori_merge_db_creation.md` records rounds 1-8,
`stutter_montessori.md` round 9 (the reproduction). This branch is the fix. Based on
`montessori_merge_db_creation`, i.e. *without* round 6's inline monitor ticking
(`7169f418b`): the monitor keeps its own thread, so there is no stutter to fix.

An earlier attempt was based on `stutter_montessori` and branched as
`numeric_pose_reads`; that was wrong -- the stutter branch never had the segfault -- and
the branch was deleted. Its one commit is the first commit here.

### Round 10 -- the numeric pose read path

57. **`NumericPose`, `NumericTransform`, `NumericPoint3`**
    (`semantic_digital_twin/spatial_types/numeric.py`) hold position/orientation, a 4x4
    with its frame, and a point, as plain numbers. The quaternion conversion takes the
    same branches the symbolic `rotation_matrix_to_quaternion` takes.
58. `KinematicStructureEntity.numeric_global_pose` reads straight from the memoized
    numpy forward kinematics. `Pose.to_position_quaternion_list` and
    `cramera.body_geometry.rounded_pose` go through it.
59. Verified against round 9's probe: `--read pose-quaternion --readers 2` crashed 6/6
    in 4.2-11.1 s before; now 60 s and 11.2 M reads clean, and 4 readers plus the 100 Hz
    writer survive 120 s. 1.5k reads/s -> 185k/s.

### Round 11 -- what the detector thread actually touches

60. **`scratchpad/segmind_monitor_casadi_trace.py`** ticks a real `build_shape_monitor`
    on a background thread and records every symbolic construction *and read* off the
    main thread, with the call chain. Reads matter as much as constructions: the crash
    lands inside `casadi::SXElem::is_constant()`.
61. **The detectors were not the problem.** Two ticks performed ~23,000 CasADi
    operations; segmind's own code accounted for 50 of them. The rest was
    `semantic_digital_twin`: `BoundingBox.transform_to_origin` wrapping each of 8
    corners in a `Point3` *and* an HTM only to call `.to_np()` again, the interval
    properties offsetting each bound symbolically, `Shape.origin` re-read per
    measurement, `global_transform.to_np()`, `center_of_mass`, and the point-of-view
    predicates compiling a CasADi function per call.
62. Converted in that order (see the commits). A tick now performs **zero** CasADi
    operations off the main thread, and takes **71 ms instead of 482 ms**.
    `MontessoriEventMonitor.start` reads the model's geometry out before spawning the
    thread, so even the one-time reads happen on the world's own thread.

### What the evidence does and does not show

- The reproducible racer (two threads in `rounded_pose`) is fixed and verified: 6/6
  crashes before, clean after.
- **The monitor-versus-planner configuration is not a reliable reproducer.**
  `scratchpad/segmind_monitor_soak.py` (monitor thread plus a thread reading
  `global_pose`) survived 90 s x3 on the *base* branch too, even with the monitor
  ticking continuously. So there is no before/after crash to show for that thread; the
  evidence for it is the instrumentation -- zero CasADi operations -- which removes the
  race by construction rather than by luck.
- This also suggests the demo's actual crash was the `rounded_pose` path, not the
  monitor.

### Known-unrelated failures in this environment

- `generate_orm.py` fails standalone with `Table '_MockedConvexSetDAO' is already
  defined`, breaking `test/semantic_digital_twin_test/conftest.py`'s `pytest_configure`.
  Worked around locally with `PYTEST_XDIST_WORKER=gw0`, which skips the regeneration;
  the collection errors and `test_part_bindings_survive_orm_round_trip` follow from it.
  **Worth the developer's attention.**
- The 12 `test/segmind_test/test_detectors` failures and the
  `PANDA_SCENE_BODIES_TO_DISCARD` import error in
  `test/experiments_test/test_franka_panda_equipment.py` are present on the base branch.

### Next

- `RotationMatrix.rotational_error` reports some rotations the long way round (`2*pi`
  minus the angle) because `to_angle` does not canonicalise; the numeric measure takes
  the shorter way. Looks like a latent bug in the symbolic version -- ask the developer.
- Still untouched, both still real: `TFPublisher` evaluating compiled CasADi from a
  state-change callback (so, on the physics thread), and `MujocoSimulator.add_entity`
  swallowing a viewer Pause that lands inside its recompile window
  (mujoco_simulator.py:1731).
- `body.global_pose` remains unsafe off-thread -- it still builds a
  `HomogeneousTransformationMatrix`. Callers wanting numbers should use
  `numeric_global_pose` / `numeric_global_transform`.
- The tick's remaining 71 ms is dominated by `random_events` set algebra
  (`SimpleEvent.__and__`/`is_empty`) in the containment and support checks, not by
  CasADi. Deliberately left alone.
- No PR opened yet.

## The numeric pose read path -- the root-cause fix for the Montessori segfault

Third branch of this line of work. `montessori_merge_db_creation.md` records rounds 1-8,
`stutter_montessori.md` records round 9 (the reproduction). This branch is the fix.

### Base, and why

Based on `stutter_montessori`, so it carries round 6's inline monitor ticking
(`7169f418b`). That commit is a workaround for the wrong cause and is what makes the demo
stutter, but dropping it here would put the crash straight back: segmind's detectors keep
`Pose` objects in their event records and compute distances and rotation errors
symbolically (`atomic_event_detectors_nodes.py:162`, `events.py:229-238`), so a monitor on
a thread of its own is still a second CasADi thread. Removing the stutter needs segmind's
detectors read numerically first -- a separate change.

### Round 10 -- the fix

52. **`NumericPose` (`semantic_digital_twin/spatial_types/numeric_pose.py`)** converts a
    4x4 numpy transform into a position and a quaternion in numpy, taking the same
    branches the symbolic `rotation_matrix_to_quaternion` takes (largest diagonal entry
    picked by the same two comparisons, same component mapping, same `0.5/sqrt(t*r33)`
    scale). cramera's own `NumericPose` moved here rather than being duplicated.

53. **`KinematicStructureEntity.numeric_global_pose`** reads a body's world pose straight
    from the memoized numpy forward kinematics (`compute_forward_kinematics_np`) and
    converts numerically, constructing nothing symbolic at all.

54. **`Pose.to_position_quaternion_list` and the transform's own** now go through
    `NumericPose`, so every caller in the repo stops running the symbolic `substitute`
    that every captured traceback landed in. `cramera.body_geometry.rounded_pose` reads
    via `numeric_global_pose`.

55. **Measured against the probe that reproduced it.** `--read pose-quaternion --readers
    2` crashed 6/6 in 4.2-11.1 s before; it now survives 60 s and 11.2 M reads. Four
    readers plus the 100 Hz writer survive 120 s and 23.3 M reads. Throughput through the
    full `rounded_pose` path went 1.5k/s -> 185k/s.

56. **Tests**: `test/semantic_digital_twin_test/test_spatial_types/test_numeric_pose.py`
    (numeric conversion equals the symbolic one for every branch, including the three
    half-turns; the list read makes no symbolic conversion; `numeric_global_pose` never
    calls `compute_forward_kinematics`) and one more in
    `test/cramera_test/test_body_geometry.py` for `rounded_pose`. 718 pass across
    `test_spatial_types`, `test_cramera` and the montessori sorting-progress tests.

### Known-unrelated failures in this environment

- `generate_orm.py` fails standalone with `Table '_MockedConvexSetDAO' is already
  defined`, which breaks `test/semantic_digital_twin_test/conftest.py`'s
  `pytest_configure`. Worked around locally with `PYTEST_XDIST_WORKER=gw0`, which skips
  the regeneration; the four collection errors and
  `test_part_bindings_survive_orm_round_trip` that follow are all downstream of it.
- The 12 `test/segmind_test/test_detectors` failures are present on the base branch too.

### Next

- **Not done, and the reason this branch keeps the stutter**: make segmind's detectors
  read numerically (`_pose_history`, `AbstractContactEvent.__post_init__`, the
  distance/rotation-error comparisons), then revert `7169f418b` and re-check whether the
  2 Hz rate limit and `--no-event-monitor` are still wanted on their own merits.
- Still untouched, both still real: `TFPublisher` evaluating compiled CasADi from a
  state-change callback (i.e. on the physics thread), and `MujocoSimulator.add_entity`
  swallowing a viewer Pause that lands inside its recompile window
  (mujoco_simulator.py:1731).
- `body.global_pose` itself remains unsafe off-thread -- it still builds a
  `HomogeneousTransformationMatrix` (`--read pose` crashed 2/4 runs in round 9). Callers
  that only want numbers should use `numeric_global_pose`.
- No PR opened yet.

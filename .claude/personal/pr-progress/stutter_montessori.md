## The Montessori demo's segfault, and the stutter the last fix for it caused

Continues the work recorded in `montessori_merge_db_creation.md` (rounds 1-8); this
branch is that one plus `7169f418b` (rounds 6-8: monitor on the plan thread, the 2 Hz
rate limiter, `--no-event-monitor`). Read that file for rounds 1-8; only round 9 onward
is recorded here. No PR opened yet.

### Plan

Root-cause the segfault properly, then undo the fixes that were aimed at the wrong
cause. Round 6 moved the segmind monitor onto the plan thread to remove a supposed second
CasADi thread, and that is what makes the demo stutter (a 99 ms detector tick against a
20 ms control period) -- so if the real cause is elsewhere, the stutter fix is to put the
monitor back and fix the actual racer.

### Round 9 -- the racer reproduced in 5 seconds, and it is neither of the two suspects

47. **`scratchpad/casadi_pose_read_race_probe.py`**: builds the real Montessori world with
    the Panda mounted (31 bodies, no MuJoCo, no publishers) and crosses two axes --
    `--mode readers/writer/both` (a writer hammering `notify_state_change()` at 100 Hz,
    standing in for `MultiSim._sim_to_world`) against `--read pose-quaternion/pose/numpy`
    (how much of the read path a reader runs). `faulthandler` is on, so a crash prints
    every thread's Python frames.

48. **Round 8's cache-invalidation hypothesis (item 45) is wrong.** The writer is neither
    necessary nor sufficient:

    | readers | writer | outcome |
    |---|---|---|
    | 1 x `pose-quaternion` | none | clean, 5 s x2 |
    | 2 x `pose-quaternion` | none | **crashed 6/6**, 4.2-11.1 s |
    | 1 x `pose-quaternion` | 100 Hz | clean, 15 s x2 |
    | none | 100 Hz | clean, 15 s |
    | 2 x `pose` (no quaternion conversion) | none | **crashed 2/4**, 13.2 s / 26.6 s |
    | 2 x `numpy` | none | clean, 30 s (30 M reads) |
    | 4 x `numpy` | 100 Hz | clean, 120 s (113 M reads) |

49. **So rounds 4-7's original premise was right after all, and round 8's probes were
    simply lucky.** Two threads reading poses corrupt the heap on their own -- no writer,
    no monitor, no TF publisher, nothing exotic. Failures are SIGSEGV or a glibc abort
    (`munmap_chunk(): invalid pointer`, `malloc_consolidate(): unaligned fastbin chunk`,
    `malloc(): unaligned tcache chunk`), i.e. genuine heap corruption, consistent with
    CasADi's non-atomic `SXNode` refcounts over shared constant nodes.

50. **Named the hot spot.** Every captured traceback lands in the *quaternion* half of
    `to_position_quaternion_list()`: `Pose.to_quaternion` (spatial_types.py:2077) ->
    `RotationMatrix.to_quaternion` (:863) -> `Quaternion.from_rotation_matrix` (:1740) ->
    `rotation_matrix_to_quaternion` -> a symbolic `substitute` over the CasADi graph
    (symbolic_math.py:678), plus SX indexing in `from_iterable` (:1604). It runs
    `substitute` even though the matrix handed to it is entirely numeric.

51. **The numeric path is immune and ~650x faster**: 943k reads/s via
    `World.compute_forward_kinematics_np` against 1.5k/s via `rounded_pose`, because it
    stops at the memoized `compute_np` result and never builds a
    `HomogeneousTransformationMatrix`. Dropping only the quaternion conversion (`--read
    pose`) turns a certain crash into an occasional one, so HTM construction races too --
    just far more rarely.

### Next

- Decide the fix. The evidence points at a numeric read path: have `rounded_pose` (and
  anything else reading poses for display or for detectors) go through
  `compute_forward_kinematics_np` and convert to a quaternion numerically, never through
  symbolic `substitute`. That is a `semantic_digital_twin` / `cramera` change, needs its
  own TDD cycle, and would make the reads thread-safe *and* ~650x cheaper.
- If that lands, **revert round 6's inline monitor ticking** -- it exists only to remove a
  second CasADi thread, and it is what causes the stutter this branch is named after.
  Re-check whether the 2 Hz rate limit (item 40) and `--no-event-monitor` (item 43) are
  still wanted on their own merits.
- Still unverified from round 6: the inline-ticking fix was never proven against a real
  long `./run_montessori_demo.sh` run.
- Untouched, both still real: `TFPublisher` evaluating compiled CasADi from a
  state-change callback, and `MujocoSimulator.add_entity` swallowing a viewer Pause that
  lands inside its recompile window (mujoco_simulator.py:1731).

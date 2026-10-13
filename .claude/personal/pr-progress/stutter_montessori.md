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

### Plan
Root-cause the segfault properly, then undo the fixes that were aimed at the wrong
cause. Round 6 moved the segmind monitor onto the plan thread to remove a supposed second
CasADi thread, and that is what makes the demo stutter (a 99 ms detector tick against a
20 ms control period) -- so if the real cause is elsewhere, the stutter fix is to put the
monitor back and fix the actual racer.

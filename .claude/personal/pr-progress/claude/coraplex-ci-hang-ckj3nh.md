## Branch `claude/coraplex-ci-hang-ckj3nh` - PR #350 (draft) - coraplex CI job hangs to the 6 h limit

Base: `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265). Label: bug.

**Root cause (found)**
`GiskardExecutable.keep_the_motions_in_step` (new on #265's branch) copies each motion's
task's life cycle onto the plan's motion node every tick. A task the chart holds through a
`PausedUntilTrue` monitor reports `LifeCycleValues.PAUSED`, which is also what
`PlanNode.pause()` sets, so `_execute_simulation`'s `if self.is_paused: sleep; continue`
read the chart's pause as the plan's and stopped ticking - and only ticking lifts that
pause. Infinite 100 Hz spin, no output, job cancelled at 6 h.

**Evidence**
- Comparing every nodeid job 103648777877 started against every one it reported leaves
  exactly one that never reported: `test_multi_robot_action_designator.py::test_elevator_navigation[stretch]`
  (gw1, 03:45:28Z). `ElevatorNavigation` is built out of two `pause_until`s.
- The notebook job triggered 8 notebooks and reported 7; the missing one is
  `language.ipynb`, whose last cell is the `pause_until` example.
- main's coraplex job is green in 17.5 min (run 34731312174) and #265 at 020cbc41a was
  green too, so it came in with #265's 111 newer commits - which is where
  `keep_the_motions_in_step` was added.

**Done**
- Failing tests: `test/coraplex_test/test_plan/test_motion_pausing.py` (commit cb3a1a635).
- Fix: leave `HELD_BY_THE_PLAN` states to the plan whether the motion is already in one or
  its task has just reached one (commit 5f9d21de2).
- Draft PR #350 opened with the session link.

**Next**
1. Read the pre-fix watchdog dump (run 34751400716, job 103708466191) to confirm the stack.
2. Confirm the post-fix run (34751416+) passes the elevator test, test_motion_pausing,
   test_language, test_executables, test_graph_parsing, test_motion_node_timing and the
   language example script.
3. Remove `.github/workflows/coraplex_hang_diagnosis.yml` and its three commits' worth of
   scaffolding before the PR is ready; keep the PR description current.
4. Report whether the coraplex job is green on the PR.

Note: no ROS in this session's container (`rclpy`/`geometry_msgs` absent, workspace packages
not installed), so nothing coraplex can be run locally; all verification is through CI.

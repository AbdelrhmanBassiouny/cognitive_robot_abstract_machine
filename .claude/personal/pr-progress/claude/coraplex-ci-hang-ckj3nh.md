## Branch `claude/coraplex-ci-hang-ckj3nh` - PR #350 (draft) - coraplex CI hang: fixed

Base `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265), label `bug`. Two commits:
d1c062e4e (tests) and e934e86c1 (fix). The temporary diagnosis workflow was rebased away.

**Root cause**: `GiskardExecutable.keep_the_motions_in_step` copied a motion task's life
cycle onto the plan's motion node every tick. A task the chart holds through a
`PausedUntilTrue` monitor reports `LifeCycleValues.PAUSED`, the same value `PlanNode.pause()`
sets, so `_execute_simulation`'s `if self.is_paused: sleep; continue` read the chart's pause
as the plan's and stopped ticking - and only ticking lifts it. Confirmed by a SIGABRT stack
dump: main thread at executables.py:396.

**Verified in CI**
- `test_each_lib (coraplex) / test`: success in 24 min on sha 0bc4e75b3 (was 6 h cancelled).
- `test_each_lib (coraplex/scripts/test_notebook_examples.sh)`: success, ~6 min (was 6 h).
- `test_elevator_navigation` passes for hsrb, stretch, tiago and pr2 - no second defect.
- 78 passed in 5m53s across test_motion_pausing, test_language, test_executables,
  test_graph_parsing, test_motion_node_timing and the elevator test.

**Outstanding**: the coraplex pytest job on the rebased head e934e86c1 was still running at
the time of writing; it runs the same code as 0bc4e75b3, which passed. Nothing else.

Note: no ROS in this session's container, so every check ran through CI.

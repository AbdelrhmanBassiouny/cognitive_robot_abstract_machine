## Branch `claude/coraplex-ci-hang-ckj3nh` - coraplex CI job hangs to the 6 h limit

**Goal**: find and fix what makes `test_each_lib (coraplex) / test` hang until the
6 h job limit on every branch stacked on #265 (#344, #346, #348, #349), plus the
sibling `coraplex/scripts/test_notebook_examples.sh` job.

**Evidence so far**
- Job 103648777877 (run 34725288521): 2 xdist workers, 496 items. gw1 finished its
  queue 03:45:28. gw0 reported PASSED for the last-but-one test 04:04:03, then the
  final test `test_publisher_lifecycle.py::test_force_torque_sensor_is_not_retained_after_stop`
  produced nothing until the cancel at 09:36:04. No pytest summary line was ever printed.
- Notebook job 103641565173: the last notebook (`location_designator.ipynb`) reported
  PASSED at 02:56:04, then silence until the cancel at 08:50:30 - treon never printed
  its summary. So both coraplex jobs stop after the last unit of work and before the
  process exits.
- `test_publisher_lifecycle.py` itself is on `main` (63d0f8a03) and unchanged since
  #265's last green run (020cbc41a); `test/conftest.py` and `test/coraplex_test/test_ros_utils/`
  are unchanged too. What did change in #265's 111 new commits and could matter:
  `MotionStatechartNode` became a `krrood` `Symbol` (graph_node.py), `SymbolGraph` grew
  an `RLock`, and `coraplex/plans/executables.py` gained per-tick motion bookkeeping.
- Cannot reproduce locally: this container has no ROS (`rclpy`, `geometry_msgs` absent)
  and the workspace packages are not installed, so `coraplex.ros_utils` cannot be imported.

**Plan**
1. [done] Temporary workflow `.github/workflows/coraplex_hang_diagnosis.yml` runs the
   coraplex tests single-process under `timeout --signal=ABRT` with `PYTHONFAULTHANDLER=1`,
   so the hang dumps every thread's stack. Three steps: ros_utils group alone, the
   lifecycle file alone, then the whole suite.
2. [next] Read the stack dump, name what blocks.
3. Write a failing test naming the behaviour (bounded stop / no thread left alive).
4. Fix the cause in coraplex (not in the test, no pytest-timeout, no skip markers).
5. Remove the diagnostic workflow, open the draft PR against
   `claude/icra-experiments-simulation-pipeline-w4ep7n`, keep its description current.

**Outstanding**: the diagnosis run (34751002125) is still in flight.

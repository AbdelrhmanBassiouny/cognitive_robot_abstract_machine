## snapshot-working-memory (icra-mechanism), PR #301

Base: `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265), not `tracy_icra` —
`tracy_icra` doesn't carry #265's content yet (confirmed via `git merge-base
--is-ancestor`); developer confirmed basing on #265. Will need restacking onto
`tracy_icra` once `tracy-demo-takes-the-integrated-branch` lands there.

### Plan (settled, full rationale in icra-mechanism/roadmap.md's 2026-09-09 section)

- `SnapshotWorkingMemory` dataclass, new module
  `experiments/src/experiments/montessori/perception/snapshot_working_memory.py`.
- Guard 1: `is_gripper_holding_something(gripper)` true → skip entirely (attachment
  already carries the grasped piece kinematically; nothing to re-perceive).
- Guard 2: `minimum_period` throttle, same shape as
  `MontessoriPerceptionNode.minimum_period` (not refactored to share it — that node is
  live robot code, out of this item's scope).
- Look via `SimulatedCamera.frame()` + `MontessoriPerceptionPipeline.detect()`, matching
  each detection to the nearest existing piece of the same `MontessoriShapeCategory`
  (greedy, one match per piece — documented simplification, not general disambiguation).
- Commit only if positional delta > `pose_change_threshold`, by writing
  `body.parent_connection.origin` directly (state, not structure) — the same pattern
  `ImaginedWorld.spawn` and `coraplex/perception.py`'s `Detection.apply_to` already use.
- Threshold: 3× measured std-dev of position noise over a static simulated scene, in a
  new test. Real-robot number explicitly deferred (no robot access this session) —
  flagged in the roadmap section, not invented.

### Done

- Fixed a real bug in `.claude/hooks/plan_item_bootstrap.py`'s `apply_item_fields`
  (hardcoded 4-space item-field indent corrupted `icra-mechanism/plan.yaml`, which uses
  2-space indent) — now derives indent from the block being edited. Regression test
  added in `.claude/hooks/tests/test_plan_item_bootstrap.py`; all 30 tests pass. Filed
  separately as `claude/plan-item-bootstrap-indent-fix`, PR
  https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/302
  (`bug` label, based off `main`) — not folded into #301; duplicated onto this branch
  too since this branch needed the fix to keep working.
- Branch cut from #265, PR #301 opened as draft, manifest recorded (`in_progress`),
  roadmap section written.
- Built `SnapshotWorkingMemory` (guard on `is_idle`, `minimum_period` throttle,
  nearest-same-category matching, delta-threshold commit via a plain
  `connection.origin` write) with 8 tests, all passing against the real MuJoCo pipeline.
- **Actually ran the tests**, not just wrote them: this container ships neither ROS nor
  a Python 3.12 environment (the workspace requires 3.12) by default. Built a dedicated
  venv at `/tmp/proj-venv312`, compiled `random_events_lib`'s pybind11 extension for
  3.12 locally (`cd random_events && python setup.py build_ext --inplace`), installed
  every missing dependency one import-error at a time, and installed system
  `libosmesa6`/`libegl1` for headless MuJoCo rendering (`MUJOCO_GL=osmesa`). Run with:
  `--orm-build=never` (this container can't build giskardpy's ORM interface — needs
  real `rclpy`). None of this is reusable state on this branch; a fresh session
  re-running these tests will hit the same missing-dependency chain and should expect
  to spend real time on it, or use a properly provisioned CI/dev environment instead.
- **Real finding, not a chosen number**: repeating a look at an *unchanging* simulated
  scene reproduces the same detected position to within floating-point noise
  (~1e-15 m) — the render is close enough to bit-for-bit deterministic that 3σ of it is
  meaningless as a gate. `POSE_CHANGE_THRESHOLD_METERS = 1e-6` is documented as a
  numerical safety margin above that floor, not a literal three-sigma figure. Recorded
  in the constant's own docstring, `icra-mechanism/roadmap.md`, and the PR description
  so it isn't mistaken later for the real (robot) measurement, which is still
  outstanding and needs physical robot access this session does not have.
- Ran `test_montessori_simulated_camera.py` (15 tests) to check for regressions from the
  relative import the new test file shares with it — none.
- Docstrings formatted (`scripts/format_docstrings.py`); PR #301 description updated to
  match; roadmap addendum appended recording the finding above.

### Next

- Nothing outstanding on this item's own scope. Remaining, tracked separately rather
  than blocking this PR: the real-robot noise measurement (needs the robot), and
  restacking onto `tracy_icra` once `tracy-demo-takes-the-integrated-branch` lands.
- PR #301 stays draft until reviewed, per standing convention.

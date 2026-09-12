# claude/answers-rendered-7aa6z6 -> PR #318 (draft)

Base: claude/icra-experiments-simulation-pipeline-w4ep7n (#265). NOT main.
Base now carries #320 (framework figure, pyrender) and the perception-pipeline
pickup demo; merged into this branch (443e13b).

## Done (commit d6647fc, on top of the earlier card commits)

The four-level card is now drawn from a RECORDED RUN, never hand-built data:
- RecordedTrial gained began_at (wall-clock start), plans (PerformedPlan),
  number. EpisodeObserver.performed(plan). Per-trial artifacts under
  trials/<n>/: joints.npz (JointTrace) and camera.mp4 + .moments.npy
  (TimedFrames). experiments/episodes/trace.py; JointTraceRecorder is a
  StateChangeCallback throttled by the observer clock.
- coraplex FIX (needs review): PlanNode.start_time was stamped at BUILD;
  nested nodes are never perform()ed (whole plan = one statechart). Now
  PlanNode.perform stamps start, CodeNode.notify stamps its own run,
  GiskardExecutable.keep_the_motions_in_step mirrors task life cycles onto
  MotionNodes after every tick (real robot: whole-chart stretch).
  Tests: test/coraplex_test/test_plan/test_plan_node_timing.py,
  test_motion_node_timing.py (cylinder_bot_world, ROS-free).
- paper: run_timeline.py = both charts in ONE figure, shared axis, rules
  "reported at", "asked at", shaded camera-frame stretch, key.
  camera_frame.RecordedFramesAround reads TimedFrames (captions with
  seconds). pose_change: PoseChangeRender.of(change, robot_at=JointPositions)
  restores joints, so the robot stands as it did. layered.py: PIL lettering,
  title band (query + answer). ObjectIdentity: SameName / montessori
  SamePiece (belief names perceived/cube_0, reality montessori/...).
- pickup_demo_mujoco: records one trial (monitor on piece_asked_about,
  question set, plans, TrialTracing joints, films with moments, keep()).
  Shove(category, along_y) = someone pushes the piece while idle -> "no" run.
  scripts/pickup_demo_cards.py runs either and writes cards.
- pickup_demo_real: rig.perform_and_record, note_event -> ticks, question
  set --ask-about, JointTraceRecorder, keep_the_episode (DB + transcript +
  trace + bag). Untested on hardware.
- scenarios: PlanStep keeps performed plan; WatchedSortingRun records plans
  and joint trace.

## Sandbox environment (redo in a fresh session)

- mujoco MUST be 3.11.0 (3.13 breaks get_joint type checks):
  python3.12 -m pip install --break-system-packages mujoco==3.11.0
- iai_tracy clone: commit 587581e (ros2-jazzy) with camera_link_joint
  origin PATCHED in the local xacro to
  xyz="0.4294 0.0026 0.8926" rpy="0.0401 1.1715 0.0327" (what the shipped
  captures imply; no public branch matches the lab's calibrated camera).
  With that test_the_camera_stands_where_the_captures_camera_stood passes.
- ORM interfaces DO build now: stubs in site-packages: ros_stubs.py/.pth
  (manufactures any *_msgs/_srvs/_interfaces, std_srvs, rcl_interfaces,
  rosidl_runtime_py), rclpy/rcl_interfaces submodules are packages,
  sensor_msgs.msg __getattr__, pip usd-core scikit-image flask.
  python3.12 scripts/regenerate_all_orm.py works (~1 min).
- env: scratchpad env.sh (AMENT_PREFIX_PATH, ROS_PACKAGE_PATH, MUJOCO_GL).

## Outstanding

- test_montessori_scenarios held-piece tests (3) failed in the full run;
  baseline check with coraplex reverted running -> see chat/PR.
- End-to-end recording demo test run (9+ min) pending at time of writing.
- test_episode_recording: 3 tests need psycopg (Postgres) - env only.
- CI not checked. No subscription, no check-in (my rules).

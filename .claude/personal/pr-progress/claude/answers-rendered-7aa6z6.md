# claude/answers-rendered-7aa6z6 -> PR #318 (draft)

Base: claude/icra-experiments-simulation-pipeline-w4ep7n (#265). NOT main - this
stacks on #265, which owns the recording pipeline the cards read.

## Plan

Rounds 1-2 (query cards; four-level event card; the user's five corrections) are
done and pushed - see the PR description.

Round 3 (the user's "not aligned / same images / wrong robot pose / real demo
data" critique + the tighter-layout feedback list), commits d6647fcb, 9a79a38b:
1. [x] coraplex: PlanNode.perform stamps start_time; CodeNode.notify stamps its
       run; GiskardExecutable.keep_the_motions_in_step mirrors task life cycles
       onto MotionNodes each tick. Tests test_plan_node_timing / test_motion_node_timing.
2. [x] episodes: RecordedTrial.began_at / .number / .plans (PerformedPlan);
       trace.py (JointTrace, JointTraceRecorder, TimedFrames); per-trial
       artifacts (trials/<n>/joints.npz, camera.mp4).
3. [x] paper: run_timeline.py (events over plan, shared axis, rules named once,
       pictured instants shaded + written on the axis), run_plan.py (PlanItem
       spans first ran part..last; ObjectIdentity/SameName; SamePiece in
       montessori/same_piece.py), camera_frame.py RecordedFramesAround with
       captions "before/after, %.1f s", pose_change.py dots along the way +
       robot_at + among, layered.py title/subtitle, lettering.py.
4. [x] pickup_demo_mujoco records a trial (monitor, plans, question set, joint
       trace, camera film with moments), Shove option; pickup_demo_real and
       WatchedSortingRun record plans + traces. Script
       experiments/scripts/pickup_demo_cards.py runs either variant.
5. [ ] IN PROGRESS: the event card stalled ~28 min on the demo's world - every
       modify_world for the ghost/dots woke CollisionManager -> pybullet
       vhacd of Tracy. Fixed (uncommitted): pose_change.ModelChangesUnannounced
       pauses every ModelChangeCallback except ForwardKinematicsManager while
       the ghost and dots stand; Callback.paused property added in
       semantic_digital_twin. --from-recording dropped from the script
       (recalled worlds point at the finished process's /tmp mesh files).
       Both demo runs relaunched sequentially (scratchpad run2/); waiting for
       the layered cards, then: send to user, run
       test_tracy_pickup_demo_mujoco.py fully, commit, push, redraft, update PR
       description (still says end-to-end verification pending).

## Outstanding / judgement calls (also in the PR description)

- JUST_FINISHED = 1.0 s, EITHER_SIDE = 1.0 s are my choices.
- Missing level is stacked as a band saying why, not dropped.
- BACKGROUND_COLOR opaque darker grey.
- Real robot: per-motion times need Giskard feedback (whole chart's stretch).
- Sandbox iai_tracy camera_link origin patched locally (environment, not code).
- Pre-existing sandbox failures: 3 held-piece scenario tests; psycopg missing
  for 3 recording tests.

## Sandbox notes

See the session summary: mujoco pinned 3.11.0; iai_tracy ros2-jazzy at 587581e
with camera_link_joint origin xyz="0.4294 0.0026 0.8926" rpy="0.0401 1.1715
0.0327"; ROS stubs in site-packages (ros_stubs.py/.pth); env in scratchpad
env.sh (AMENT_PREFIX_PATH=/home/user/ament_ws, ROS_PACKAGE_PATH
iai_tracy_description:ur_description:robotiq_description, MUJOCO_GL=osmesa);
`python3.12 scripts/regenerate_all_orm.py` builds ORM interfaces (~1 min).
Tests: `MUJOCO_GL=osmesa python3.12 -m pytest <paths> --orm-build=never`.
A demo run alone: ~12 min (picked up) / ~8 min (shoved); running two in
parallel roughly triples both.

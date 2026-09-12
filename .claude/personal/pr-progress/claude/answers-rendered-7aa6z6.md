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
5. [x] a1c216f - event card stalled on the demo's world: every modify_world
       for the ghost/dots woke CollisionManager -> pybullet vhacd of Tracy.
       pose_change.ModelChangesUnannounced pauses every ModelChangeCallback
       except ForwardKinematicsManager while they stand; Callback.paused
       property in semantic_digital_twin. --from-recording dropped from the
       script (recalled worlds point at the finished process's /tmp meshes).
6. [x] dbf02c0 - merged the moved base (RecordedMotion/ObserverMotionListener,
       HaveTheRobotAct steps with motion_listener, LiveTracy.connected,
       PerceivedScene). HaveTheRobotAct now also carries `performed` (my
       PlanStep folded into it); real demo main = LiveTracy + my recording.
7. [x] 0e78af8 - first relaunched demo run was OOM-killed at 13.8 GB drawing
       the card: TimedFrames.read loaded all 2946 film frames (4.4 GB) on top
       of the run's own copy. TimedFramesFile reads one frame at a time;
       TrialArtifacts.camera returns it; FramesByMoment ABC.
8. [x] 49cb3de - unit tests for SamePiece/kind_of.
9. [x] e4a17f0 - first real card showed two defects: PoseChange.around read
       the object's whole life (pick-up drawn ending inside the board) and the
       camera frames were +-1 wall-clock s (identical in a 10x-slow sim). Now
       MotionStretch (Translation..StopTranslation of the object, the one the
       event falls in / nearest) drives the ghost+dots+robot_at(over.end) and
       the camera frames (FramesByMoment.last_at_or_before / first_at_or_after
       -> TimedFrame with its moment; captions + chart use the real instants).
       EITHER_SIDE removed. PickUpActionMujoco/PlaceActionMujoco now
       ManipulatesBodies so the plan chart picks the accounting item out.
10. [x] run4 card showed: ghost invisible (copied Mesh shapes kept origin on
       the original body -> drawn on the object) and camera looked along the
       carry (poses hid each other). Fixed: _copied re-frames origins on the
       ghost; PoseChangeRender.hang_a_camera_across (viewpoint_across,
       MujocoCamera.pose_looking_from, OVERVIEW_VIEWPOINT const). Also the
       card now emphasises PickUpEvents only (PlacingEvent made the place item
       amber too). RenderedScene.pixels_of. NOTE MujocoSim build re-roots the
       world (world.root changes) - take a hung camera off camera.body.
11. [x] user feedback on the preview: images+simulation at the translation's
       start/end (done via MotionStretch), the question asked directly after
       the translation ends, a view showing ghost+object+trail. Done:
       questions/after_the_move.QuestionAfterTheMove (both pickup demos; asks
       on StopTranslationEvent of the asked piece, else at the end);
       viewpoint_across(away_from=robot base); framed on subject+ghost+dots+
       boards (other pieces dropped from scene_around).
12. [ ] IN PROGRESS: demo runs scratchpad run6/ (~35 min). Then: send both
       layered cards, run test_tracy_pickup_demo_mujoco.py fully (alone),
       redraft, update the PR description (pr_body.md drafted; fill
       "Verified").

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

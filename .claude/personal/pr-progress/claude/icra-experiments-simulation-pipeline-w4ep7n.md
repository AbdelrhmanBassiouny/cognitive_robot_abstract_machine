## #265: record_episode runs on the fetched world and the look (2026-09-12, day)

**Session.** https://claude.ai/code/session_01GCgvcENQygfenibC73KQ1n -- the same session
as the pickup demo work below; resume here.

**The task, in the developer's words.** "Improve the record_episode to have an option to
use the real fetched world and look. Test it very well and make sure it is clean and
reliable."

**What `--execution real` was.** The world was built from the URDF (`TracyOnItsOwnTable`),
the pieces stood by a seeded layout, MuJoCo ran on it and the questions were answered
from that pretend scene; only the perturbation prompt was real. `SortingScene._perform`
also runs every robot action under `simulated_robot` whatever the execution type.

**Done.**
- `record_episode --scene {built,perceived}` (`SceneChoice`): `perceived` fetches the
  world from the robot and stands the board and the pieces in it by looking
  (`TracyLookingAtItsOwnTable` in `scene_builder.py`, over `PerceivedScene` in
  `scene_publishing.py`); needs `--execution real` (`PerceivedSceneNeedsTheRobot`) and
  its layout is `--layout as-found` by default (`PerceivedSceneCannotBeLaidOut` for any
  other). Exit code 2 for clashing choices. Tomorrow's command:
  `python experiments/scripts/record_episode.py --execution real --scene perceived
  --scenario scene-stands-still --perturbation piece-shoved --piece cube [--record-bag]`.
- `Layout` (ABC) in `scenarios.py`: `PieceLayout` (stated) and `LayoutAsFound` (read off
  the built scene, `PieceLayout.read_from`). The scenario keeps `layout` (how the pieces
  come to stand) and `starting_layout` (where they stood when the trial began,
  `SceneNotBuiltYet` before a build); goals and the watched run read the latter.
- `ScenePhysics` (ABC): `SimulatedScene` and `RealScene` (settle/stop do nothing). A
  REAL scenario builds a `RealScene`; `filmed` + REAL raises `RealRunCannotBeFilmed`;
  the three scripts whose steps need the simulation (`runs_on_the_robot = False`) raise
  `ScenarioRunsOnlyInSimulation` under REAL. `MontessoriSortingScenario.simulation` is
  now `physics`. `MontessoriWorldBuilder.build` returns the `World`; builders state
  their `piece_set`.
- `SortingScene.stand_the_piece_at` moves a piece on a fixed connection (a perceived
  piece) by restating the weld, and keeps the piece's turn (it used to reset it).
- `PiecePublisher.take_down()`; `PerceivedScene.perceive()` takes the previous look's
  pieces down first, so a second trial looks afresh. `PerceivedSorting` now composes a
  `PerceivedScene` (pickup_demo_real and pickup_demo_mujoco adapted).
- `LiveTracy.connected(node_name)` (`tracy_experiments/live_tracy.py`): one connection
  to the robot (executor thread, fetch, VizMarkerPublisher before WorldSynchronizer,
  `build_node`) shared by `pickup_demo_real`, `perception/node.py` and `record_episode`.
- Race fixed on the live node: `hold_board` used to replace `look.pipeline` while the
  node's cached newest scene was one taken without the lid; `RepeatedLook.read_with` /
  `MontessoriPerceptionNode.read_with` now forgets the stale result, and
  `look_at` keeps a result only if the pipeline it was taken through is still current.
- `Episode.planned(scenario_type, execution_type, ...)`; `from_run` delegates to it.
- generate_orm ignores `scene_publishing` and `live_tracy`; ORM regenerated.

**Tests.** `test_tracy_montessori_scene_builder.py` (new, 11): both builders, the
as-found layout against the tape truth on `scaled_pieces_in_a_row` in `parse_tracy()`'s
world, and a watched REAL run over the perceived scene (RealScene, no synchronizer,
question set asked, a shove prompts the person and disturbs the scene, two trials look
afresh). `test_record_episode.py` 51, `test_montessori_scenarios.py` 81,
`test_montessori_scene_publishing.py` 9, `test_montessori_live_camera.py` 15 (three new
on `read_with`/`look_at`).

**Open for the developer.** (1) On a perceived run the perturbation still moves the
*model* (the runner's design): the run does not look again after the person acted, so
the question set is answered from the model as moved, not from a second look. A re-look
at the answer step is the honest next step if the recording should show perception
under perturbation. (2) `RobotSortsAPiece`/`PieceHeld...` are refused under REAL until
the real rig (Robotiq gripper, `PickUpAction` on a two-armed robot) is wired into a
`ShapeSorter` for the scenarios. (3) Not run on the robot (powered off).

## #265: the pickup demo runs on the perception pipeline, real and in MuJoCo (2026-09-12)

**Session.** https://claude.ai/code/session_01GCgvcENQygfenibC73KQ1n -- resume here.

**The task, in the developer's words (2026-09-11 evening).** "Now I want the pickup demo
real to fully work with the perception pipeline, you cannot use the robot now as I
powered it off. So do what you can and test what you can until I come back. Also do a
full simulation based test in mujoco similar exactly to the real one. And record mujoco
videos and save them and show them to me. Commit your work after testing it and push,
also don't forget to fetch any updates to pr 265 as it is being updated regularly. I
will be using PR 316 (it is soon going to merge into PR 265) to record tomorrow so make
everything ready for it."

**Done.**
- `scene_publishing.py` (was `board_publishing.py`): `look_for_board`, `hold_board`
  (finds, stands, and hands the look a pipeline reading the lid), `PiecePublisher`
  (stands each piece the look put on the table as the known piece, resting on the
  surface -- the depth's own height reading is not used, it sinks a body into the
  table). `RepeatedLook` in `scene_source.py` is the base of the node and of
  `RecordedFrame`. `NoBoardInView` in `exceptions.py`.
- `pickup/perceived_sorting.py`: `PerceivedSorting` (perceive -> stand -> release pose
  over the perceived board's hole) with a `ShapeSorter` the real rig and the MuJoCo rig
  implement. Tested on `scaled_pieces_in_a_row` against its tape truth: board corner and
  all four pieces within 15 mm.
- `pickup_demo_real.py` rewritten on it: no hand-placed constants, `_SortingRig` is a
  `ShapeSorter`, main looks (30 looks for the board), prompts, sorts. Not run on the
  robot (powered off).
- `pickup_demo_mujoco.py`: reality (Tracy + board at tape centre (1.045, 0.159) +
  smaller set at x 0.79, y 0/0.1/0.2/0.3) vs belief (Tracy alone); camera on
  `camera_link` at the captures' optical pose (`CAMERA_LINK_T_OPTICAL`, pinned by a
  test); perception publishes into the belief within 1 mm; actuator-driven sorting via
  `PickUpActionMujoco`/`PlaceActionMujoco` on a `Context(belief)`, the belief's joints
  following the simulation (`RealTimeSimulation.followers`); films (side view + robot
  camera) and the detections picture written by `write_artifacts`.
- Three MuJoCo fixes found on the way: the shoulder links sink 40 mm into the table's
  pedestal box and pinned the pan joint (`LINKS_SUNK_INTO_THE_TABLE` in equipment.py);
  `close_gripper_around` now aims at the narrowest width and stops on any shared
  fingertip contact + 1 mm squeeze (the belief body's name is not the reality's);
  `MujocoGeom.contact_dimensionality` (condim) new in sdt, loose pieces get 4.
- Result: cube, cylinder, rectangular prism go through their holes every run (~60 s
  unfilmed, ~85 s filmed). The triangular prism slips out of the parallel pads on the
  carry (face + opposite edge; firmer squeeze ejects it; condim 6 dropped it on the
  lowering). Strict xfail with that reason.

**State at the end of the session.** Committed as `97223f4f1` (amended `e4b8167d8`),
the remote's `d2a39f92b3` (PR #316 merged into #265 by its own session) merged in as
`723d3cb449`, pushed to `bass`; #316's branch fast-forwarded to the same tip and pushed
(GitHub already shows #316 as merged). PR #265 description has a section for this
session; still a draft. Full `test/experiments_test` on the pre-merge tree: 1194
passed, 4 failed (two caplog ones #316 also lists, `test_real_stretch_demo_process_boundary`
which fails on the pre-session tip too, one order-dependent `test_episodes` that passes
alone); on the merged tree the 316-touched modules plus this session's: 77 + 89 passed,
1 xfailed. Videos in `~/pickup_demo_videos/2026-09-12_perceived_pickup/`. The first
`save-plan.sh` of this session reverted two other sessions' plan entries (stale
CLAUDE.local.md copy -- the hazard the notes warn about); repaired from `25f6f9483d`
plus this session's additions, dashboard republished.

**Open for the developer.** (1) Run `pickup_demo_real` on the robot: check the perceived
board and pieces in rviz before pressing Enter; gripper close setpoints
(`grasp_widths.py`) were tuned for the 30 mm set -- the 16 mm rectangular prism may need
more than 0.6. (2) The triangular prism's simulated grasp. (3) #316's
`record_episode --execution real` still builds its world from the URDF
(`TracyOnItsOwnTable`), not from the fetched world + perception; wiring
`PerceivedSorting` into a `MontessoriWorldBuilder` is the next step if tomorrow's
recording should perceive.

## #265: live shape and hole detection is wrong on the new 80 % pieces (2026-09-11, done; bringup restarted 21:47)

**Session.** https://claude.ai/code/session_0186xZo3eqCDVcqhi1E3LHdY -- resume here if
anything breaks. Memory note `perception-position-offset-stopgap` holds the earlier
diagnosis (live detections ~0.3 m toward the camera; extrinsics/intrinsics/frame_id/
table height ruled out; stopgap only on `icra_final`).

**The task, in the developer's words (2026-09-11).** "We working on fixing the perception
detection of the shapes issue ... the sample images I showed you where the detections are
wrong, the objects btw are new they are scaled down to 80 % so for example the cube side
length is now 22.4 mm instead of 30 mm. Also the ground truth positions of the current
situation is as follows all at the same x value of 79 cm while the y values are (cylinder
10 cm, triangle 20 cm, rectangle 30 cm, cube 40 cm). We want to take captures now and
save them with tests that compare against the ground truth. The board front left corner
is at (99, 40) cm where the side with the drawers and handles are toward the shapes and
it is fairly horizontal along the y axis (same x value in each horizontal (long) side).
We need to find the issue in the hole detections and the shape detections and fix them.
Also save this prompt here in the repo and add this conversation and session in the
history so I can resume later if something happens."

**Ground truth of the table as set up on 2026-09-11** (reference frame, metres):
pieces all at x = 0.79: cylinder y = 0.10, triangular prism y = 0.20, rectangular prism
y = 0.30, cube y = 0.40. Board front-left corner at (0.99, 0.40); the drawers-and-handles
side faces the pieces; long sides run along y at one x each. Pieces are the new set at
0.8 of the measured ones (cube 22.4 mm instead of 30 mm).

**What the two screenshots (17:46, 17:55) show.** The board box is found, but the hole
labels (`cube`, `cylinder`, `disk`, `triangular_prism`) sit on the wrong holes and only
four or so holes are boxed; of the pieces on the table only the triangular prism is
detected (green), the cyan cube and yellow rectangular prism get no box at all.

**Uncommitted at session start** (files 18:24): `perception/live_camera.py` (`LiveCamera`,
`CameraPoseLookup`) and `perception/capture_from_camera.py` (CLI writing one live look as
a `SceneCapture`). `node.py` still has its own duplicate subscriptions/`TFWrapper`. No
tests for either yet. No new capture written yet.

**Found 2026-09-11 evening (root cause).** The published `table -> camera_link` transform
(`iai_tracy_description/urdf/tracy.urdf.xacro`, commit `db06ecf` of 2026-04-30, "new
calibration for camera_link", xyz `0.410542 -0.015143 0.932933` rpy `-0.046277 1.378820
-0.050299`) is stale: the camera has physically moved since. Measured off the depth of
*every* shipped capture and the new one alike: the table's normal is 22.9-23.0 deg off
the optical axis (published: 11.0 deg) and the camera stands 0.892-0.894 m above the
table (published 0.935). Projecting the robot's own gripper (TF `l_gripper_tool_frame`)
into the picture with the published pose lands ~240 px above the real fingers; with the
fitted pose it lands on them. Fitted pose in `map` (optical frame, 4x4) is saved in the
scratchpad as `T_new.npy`; as a `camera_link` origin in the `table` frame it is
xyz `0.4264 -0.0206 0.8938` rpy `0.0400 1.1716 0.0326` (tilt+height from the table plane,
x/y from the gripper pixel, yaw kept from the URDF). *The URDF must be recalibrated; that
is outside this repo.* With the fitted pose: the pieces deproject to x 0.788-0.793 and
y 0.014/0.111/0.209/0.305 against the tape's 0.79 and 0/0.10/0.20/0.30 (corrected by the
developer: cylinder 0, triangle 0.10, rectangle 0.20, cube 0.30; board front-left corner
(0.99, 0.30)); the board is found at x 0.986-1.100, y 0.021-0.305 with the mesh at scale
1.0 and all six holes on their openings. `BOARD_SCALE_AGAINST_THE_MESH = 0.865` is an
artefact: the wrong tilt reads the board at 0.81 (x) x 0.92 (y) of its size, mean 0.865.
The tuned workspace (`tracy_workspace.json`, max x 0.915) also excludes the true board.
The new pieces are 0.8 of the old set (cube 22.4 per the developer; cylinder 22.4,
rectangle 16x32, triangle side 29.6, ~24 tall) and a different colour: hue 98 (was 86,
cyan) and 26 (was 21; note 26 is also the board's wood). With pose + scale 1.0 + a 0.8
set with those hues, all four pieces are detected within 1 cm of the tape.

**State at the end of the session.** `HEAD` of the branch (after `58eb1f2f4`: the uniform 0.8 set, then the tape-refined pose), pushed to `bass` (with the
bass key, see memory `git-push-needs-bass-key`); the other session's main merge
(`7af6ce068`) merged in. Commits: `1655b0e42` LiveCamera + capture_from_camera (+11
tests); `746f8ea3c` the camera pose, board scale, workspace, opening-from-measured-
surface, seed reach 0.06, KnownPieceSet (FULL_SIZE_PIECES / SMALLER_PIECES), CaptureTruth
with tape places, tape tests; `58eb1f2f4` to_json kwargs. Montessori suite in this venv
(`--orm-build=never`, ignoring the two untracked leftover test files): 775 passed, 11
xfailed, 0 failed. PR description **not** updated (no gh here); PR still a draft.

**Recorded as known misses (strict xfail, owned by competing-explanations):**
`TABLE_PIECES_STILL_MISREAD` = `stuck_cube_in_hole` (side-on cylinder read as a cube)
and `displaced_cube_from_hole` (cylinder leads the cube by 0.074 < 0.075, nothing
reported). With the tape-refined pose (camera 9 mm lower in y) the cylinder in its hole
on `tracy_pickup_demo` is fitted again, so all 27 narrowing tests pass unmarked. Suite:
780 passed, 6 xfailed. Fitted optical pose: `~/workspace/T_new_camera_pose_20260911.npy`.

**URDF, applied 2026-09-11 22:00 -- bringup restart still owed.** Two ROS overlays exist
and the sourced one is `~/workspace/ros/install` (first on `AMENT_PREFIX_PATH`, merged
install, built from `~/workspace/ros/src/iai_tracy`); `~/ros2_ws` is second and its
install was never rebuilt. The developer's edit went to `~/ros2_ws/src`, so the running
`robot_state_publisher` (launched 18:53) still served the old numbers -- verified from
its `robot_description` parameter and `tf2_echo table camera_link`. The new origin
`<origin xyz="0.429417 0.002602 0.892603" rpy="0.040005 1.171431 0.032689"/>` is now in
`~/workspace/ros/src/iai_tracy/iai_tracy_description/urdf/tracy.urdf.xacro` (old line
kept as a comment) and `colcon build --packages-select iai_tracy_description
--merge-install` installed it. Reloading it into the live publisher was refused by the
classifier, so the developer restarts `ros2 launch iai_tracy_bringup tracy_ros2.launch.py`.

**Both symptoms of the 20:45 screenshot are the stale pose, not the code.** The
screenshot predates the edit (21:16). Re-running `scaled_pieces_in_a_row` with the pose the
live tree still publishes reproduces it exactly: the board box drawn below the lid's
picture, and three extra yellow "pieces" (two triangles, a rectangle) on the drawer front
inside the board outline at lid height -- the drawers are wood of hue 26, the smaller
set's yellow. At the fitted pose the same capture draws the box on the lid and reports
four pieces and nothing else. The overlay already draws each box with its parallax
(`RectifiedView.to_pixels` at surface and top height).

**Added so this cannot go unnoticed again** (commit after `d4e8edb41`):
`CameraPoseError` in `measured_plane.py` (`tilt`, `height`, `within_tolerance` at
`LEVEL_TOLERANCE` 1 deg / `HEIGHT_TOLERANCE` 1 cm, moved there from the captures test);
`MontessoriPerceptionNode.check_camera_pose` runs it on the first placed look, keeps it as
`camera_pose_error` and logs a ROS warning naming the tilt and height when it is off;
`capture_from_camera` prints it after writing. Tests in `test_montessori_measured_plane`
(leaned / lifted captures), `test_montessori_live_camera` (the node keeps the error).

**Bringup restarted 21:47 and the pose is live**: `tf2_echo table camera_link` reads
0.429 0.003 0.893 and a live capture measures the table 0.4 deg / +1 mm off, within
tolerance.

**The flicker (screenshots 21:42-21:45: one frame right, the next with the board box
and holes a row out).** Reproduced on an 8-frame burst off the live camera at 21:55:
6 of 8 frames fitted the board at x 1.066, yaw 12.5 deg, holes on the wood (fine-fit
agreement 0.43); 2 at x 1.045, yaw -0.5 deg, holes on their openings (0.80). Cause:
`BoardDetector` seeded the layout fit at the *mean* of the hole-sized dark patches and
let it move at most `seed_reach` = 60 mm from there. Only 4 of the 6 holes read dark
(the two nearest the camera are lit), so even on a good frame the mean lay 45 mm from
the board's centre; on the bad frames the shadow under the lid's left rim (y 0.302, the
lid's edge) came out as a 5th hole-sized dark patch, the mean moved to 68 mm and the
right placement fell out of reach, so the rough grid took the best in-reach placement --
the layout turned a twelfth of a turn and shifted 21 mm. The spurious yellow
"triangular_prism"/"rectangular_prism" on the drawer front in those frames are the
same defect: a misplaced board leaves the drawer wood (hue 26 = the smaller set's
yellow) unclaimed by `table_hidden_by`. Fix (`4bf6694f1`): each opening is
one of the holes, so `BoardHoleLayout.origins_with_a_hole_at(openings, yaw)` names
where the board would stand for every (opening, hole) pairing, and
`OutlineFitter.fit_among(CandidatePositions...)` takes the best of those over the full
circle of coarse turns, then settles it as before; `seed_reach` and
`PerforatedSurface.middle` are gone. Missing holes and false patches no longer move the
seed. Measured: all 8 burst frames now at (1.045, 0.156-0.157); the 7 shipped captures
fit within 0-4 mm of their previous placement at the same agreement; the rough pass
costs 0.04 s against 0.10 s. `burst_00` is shipped as capture `shadowed_lid_rim` (same
scene and tape truth as `scaled_pieces_in_a_row`); before the fix it failed 5 of the 15
capture tests (holes, corner, tape places, drawer-front pieces). Unit tests in
`test_montessori_board_layout` for the origins and `fit_among`. Still per-frame:
`burst_04` misses the real triangular prism (strength below the lead) -- a piece
detection miss, not the board.

**Open for the developer.** (1) Done: bringup restarted, pose within tolerance; run the node and check no
"published pose is off" warning is logged (or take a capture: the CLI prints the error).
Until then the live node is ~0.2 m off in x -- do not resurrect the `icra_final` stopgap.
(2) Answered: the board is 80 mm by tape, so the 7 mm the depth reads
the lid low is the sensor's (the opening-against-measured-surface change covers it).
(3) Answered: the cube is 24, so the smaller set is a uniform 0.8 (commit after
`58eb1f2f4`). (4) Answered: with the tape-refined pose all 27 narrowing tests pass on
`tracy_pickup_demo` unmarked, so nothing moves. (5) Untracked leftovers still in the tree:
`pickup_demo_perceived_board.py` + its test (collection error), `test_montessori_shape_bodies.py`,
the 37 GB `.mcap` dir, `ganttchart.pdf`, `.mcp.json`, and an uncommitted edit to
`semantic_digital_twin/scripts/create_postgres_database_and_user_if_not_exists.sql`.

**Plan as executed.**
1. Finish `LiveCamera`: `MontessoriPerceptionNode` reads through it; mocked tests for
   `LiveCamera`/`write_capture`. Commit.
2. Take captures off the live camera with `capture_from_camera.py`, ship them under
   `resources/captures/`.
3. Table-plane fit module + a test that every capture's depth agrees with its stated
   pose (fails today); rewrite all seven captures' `reference_frame_T_camera` to the
   fitted pose.
4. Board mesh at its own size (drop 0.865); workspace re-tuned to reach the board.
5. A known-piece *set* the pipeline is handed (old set for the shipped captures, the
   0.8 set with its hues for the new capture and the live node).
6. `CaptureTruth` with positions; ground-truth tests on `scaled_pieces_in_a_row`.
7. Re-run the whole montessori suite; re-measure whatever the corrected pose moves.
8. Update this note and the PR description; push; keep #265 a draft. Tell the developer
   the URDF numbers.

# #265 — integrated-simulation-pipeline (plan icra-foundation)

## Plan for this session (/plan-item-resolve, auto mode)

The item was stalled, not on review and not on a failing check: the branch had
conflicted with `main` since 2026-09-07, so the stack maintenance routine labelled
#265 `needs-resolution` and skipped it on every pass after — twelve comments, nobody
picking it up, and the manifest saying `in_progress` with no mention of it.

1. Record the real blocker on the item before resolving anything. — done
2. Merge `main`, resolving the two conflicting files. — done
3. Sweep for the stale readers git cannot flag, per the roadmap's standing hazard. — done
4. Test first, then fix, then push; keep #265 a draft. — done
5. Update roadmap, manifest, PR description, dashboard. — done

## Done

- **`b5e2e2669` merges `main`.** Two conflicts: an import union in
  `test/coraplex_test/test_plan/test_executables.py` (this branch's `ExecutionType`,
  main's `Context`, both used), and `world_description/geometry.py`, where main's
  `f4c15c243` gave every `to_json` a `**kwargs` parameter while this branch's
  `Shape.to_json` names its four fields because a `finish` is a `StrEnum` the generic
  `_serialized_fields` reading does not restore. Kept this branch's fields and main's
  keyword arguments.
- **The hazard's fourth instance, first as a signature.** `Sphere`, `Cylinder` and `Box`
  override `to_json` on this branch and on no ancestor of `f4c15c243`, so git reported no
  conflict for them, and `ShapeCollection.to_json` — which hands its shapes the keyword
  arguments it was given — raised
  `TypeError: Box.to_json() got an unexpected keyword argument` for any shape of a body
  serialized with a `ReferenceWriter`. Migrated all three plus `Shape` itself.
- **Test written first**:
  `test_a_shape_is_serialized_where_its_frame_is_written_as_a_reference` in
  `test/semantic_digital_twin_test/test_adapters/test_json_parsing.py`. It fails on the
  merge without the migration with exactly that `TypeError`.
- **The roadmap's field-diff sweep was run and came back clean** — of the nine names
  `main` removed, every one is still defined there, so all nine were moves.
- **Measured** (python3.12 venv, `CRAM_ORM_BUILD=never`): `test_json_parsing.py` 41
  passed; `test/semantic_digital_twin_test` 1097 passed against 1082 on the pre-merge tip
  with the identical 41 failures; `test/krrood_test` 2952 passed with the same four
  failures the pre-merge tip has there.
- `mergeable_state` is `unstable` rather than `dirty` — the conflict is gone.
- Roadmap section, manifest `blockers`/`notes` and the PR description are all updated;
  #265 is still a draft.

## Next / outstanding

- **CI is running on `b5e2e2669` and nothing is armed to watch it** (standing rule). It
  is the first run this lineage has ever had: `db9561fa6` carried zero check runs and no
  commit status, so the `tracy_icra` merge, both earlier `main` merges and the #304 merge
  have never been exercised by CI. Read the run directly.
- The `needs-resolution` label clears itself on the next maintenance pass.
- Still open from before, untouched: `SimulationTimePacer.sleep()` is unbounded — what a
  stalled simulation should do is the developer's call.
- Writing the PR description through the GitHub MCP server escapes the backticks in the
  `## Promote` block, so each write grows the stray run of backticks around the link. The
  URL is intact; the block is the stack tooling's own.

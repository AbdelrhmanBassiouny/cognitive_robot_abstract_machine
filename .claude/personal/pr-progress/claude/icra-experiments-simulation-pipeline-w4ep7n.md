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

## #265: the experiments CI job, red on a role taker the ORM dropped (2026-09-11 night, done, pushed)

**Session.** https://claude.ai/code/session_0155Lgy4BZ7QcZHiRuxxJJyA

**Asked.** "CI on experiments failed due to a role taker issue, fix it", with the
`AttributeError: all_role_takers` traceback from run 34627474746's experiments job.

**Plan, and what it turned out to be.** Read the job log rather than trust the error's own
name: `all_role_takers` is a property reading `self.role_taker`, so an `AttributeError` from
inside it is rewritten by the interpreter into one about the property. The field was simply
never mapped — ORMatic skips any field typed as a generic with free parameters, and
`RecordedQuery` is a `Role[Question]` where `Question` is generic. Reproduced in krrood's own
dataset in four tries (plain role, role over a concrete JSON value, role over an
unparameterized generic JSON value — the third reproduces), fixed in
`WrappedTable.parse_field`, pinned by three krrood tests written first.

**Done.** `5d9049212`, merged onto the branch's new head as `e976addc2` and pushed. PR
description has a new section; `plan.yaml`'s CI blocker and `roadmap.md` are updated
(2026-09-11 night section); dashboard republished.

**Next steps.** Read the CI run on `e976addc2` directly — nothing is armed to watch it. The
fix is in `krrood`'s generator rather than in anything #265 introduces, so if the developer
would rather review it separately it is one commit and cherry-picks cleanly.

**Container note, now out of date in every earlier entry.** This container *can* build the ORM
interfaces now: `scratchpad/stubs/sitecustomize.py` stands in for the ROS packages and `pxr`,
plus `piqp`, `rtree`, `scikit-image`, `transforms3d`, `opencv-python-headless`, `mypy` and a
copy of the repo's own `random_events/plotting.py` into the installed wheel. `psycopg`, an
`imageio` video backend and a real ROS install are still missing.

## #265: live shape and hole detection is wrong on the new 80 % pieces (2026-09-11, done, pushed)

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

**URDF line for the developer to apply** (the auto-mode classifier refused to write into
`~/ros2_ws/src/iai_tracy`): `tracy.urdf.xacro` line 111 ->
`<origin xyz="0.429417 0.002602 0.892603" rpy="0.040005 1.171431 0.032689"/>`, then
`colcon build --packages-select iai_tracy_description` and restart the bringup.
Composed through the live `camera_link -> camera_color_optical_frame` (3.2 cm offset).

**Open for the developer.** (1) Apply the URDF line above; until then the live node is ~0.2 m off in x -- do not resurrect the
`icra_final` stopgap. (2) Answered: the board is 80 mm by tape, so the 7 mm the depth reads
the lid low is the sensor's (the opening-against-measured-surface change covers it).
(3) Answered: the cube is 24, so the smaller set is a uniform 0.8 (commit after
`58eb1f2f4`). (4) Whether the narrowing
demonstration should move to `scaled_pieces_in_a_row` (all four pieces found) instead of
staying xfailed on `tracy_pickup_demo`. (5) Untracked leftovers still in the tree:
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

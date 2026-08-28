## Branch `tracy_icra` - Montessori perception over the wifi link

Committed as `ea1f6f73a` and `5865ecb03`, pushed to `origin/tracy_icra`. Note the branch's
configured upstream is `sorin/tracy_icra` (a colleague's fork); the push went to
`origin` by explicit choice and the upstream was left pointing at sorin.

### Diagnosis (done)
The node subscribed to the raw streams `/camera/color/image_raw` and
`/camera/depth/image_raw`. This camera publishes 1920x1080, so a raw colour frame
is 6.2 MB and a raw depth frame 4.1 MB. Measured over 15 s on the raw colour
topic: 251,490 IP fragment reassembly requests, 117 succeeded, 249,438 failed
(99.95%). Small messages on the same link were fine throughout
(`/camera/color/camera_info` at ~28 Hz), which is what ruled out discovery,
domain, QoS and firewall as causes.

Two things confused the picture early on and are worth remembering:
- The `ros2` daemon serves a cached graph, so `ros2 topic list` kept showing the
  full robot topic list while real discovery (`--no-daemon`) saw nothing. A topic
  list is not evidence that anything is reachable.
- `ros2 topic hz` on an `image_transport` sub-topic can report nothing simply
  because the publisher is lazy and the probe gave up before it activated;
  `compressedDepth` looked dead this way but is fine with a real subscriber.

### Done
- `camera.py`: `ImageTransport`, `CompressedImageFormat` (parses the `format`
  field), `DepthQuantization` (the `compressedDepth` header), and
  `decode_compressed_color_image` / `decode_compressed_depth_image`.
- `exceptions.py`: `UndecodableCompressedImage`.
- `node.py`: reads `/camera/color/image_raw/compressed` and
  `/camera/depth/image_raw/compressedDepth`; decoding moved out of `_build_frame`
  into `_on_color`, so a frame is shown even when the transform tree cannot yet
  place the camera.
- `viewer.py`: `CameraFrameViewer` plus an `ImageDisplay` abstraction over
  OpenCV's windowing, so the drawing logic is testable without a screen. Exposed
  as `--show-images`.
- 43 tests in `test_montessori_perception.py`, 83 across the montessori files.
- Verified live: colour and depth both decode and render off the real camera.

Measured transports on this camera: colour compressed 18.9 Hz / 3.83 MB/s;
`compressedDepth` PNG ~118 kB per frame. `/camera/depth/image_raw/compressed` is
JPEG-mono8 and publishes a 0-byte payload, so it is not usable for depth.

### `json_msgs` - investigated, nothing to port
The user recalled a fix on `claude/cramera-voice-questions-ttwcza`. There is
none: local and origin are the same SHA, there are no stashes, and every ref in
the repo that has `feedback_publisher.py` imports `json_msgs`. It is a real ROS 2
package living in `cram2/cram_ros2_packages` (confirmed by cloning it), which
`.github/docker/setup_workspace.py` clones for CI but which is absent from the
local `~/Projects/ros2_ws`. So it is an environment gap, not a repo bug, and it
does not warrant a bug-fix PR. Fix is to build that package locally.

### `watch_camera` (done, commit `5865ecb03`)
`python -m experiments.montessori.perception.watch_camera` subscribes to the two
camera streams and draws them, with no world fetch and no transform tree, so a
silent camera and an absent robot no longer look alike. Verified against the live
camera with a recording display standing in for the screen: both windows drawn at
960x540.

The viewer's `show(color, depth)` became `show_color` / `show_depth` for this, so
one dead stream leaves only its own window empty. That case is real - the depth
stream's plain `compressed` transport publishes a 0-byte payload.

### `json_msgs` - fixed in the environment
Built into `~/Projects/ros2_ws`. Two things bit on the way: the package lives in
`cram2/cram_ros2_packages` (not this repo), and the first `colcon build` picked
the `cram2` virtualenv's python, which has no `empy`, so `rosidl_adapter` failed
with `No module named 'em'`. The system python has `empy` 3.3.4 and `lark`, so
the build has to run with the venv off the PATH - and because CMake caches
`_Python3_EXECUTABLE`, `build/json_msgs` had to be wiped before reconfiguring.
`test/experiments_test/` now collects; the 5 remaining failures there are the
documented empty-ORM-interface state (`NoDAOFoundError`), fixed by
`scripts/regenerate_all_orm.py`, not by anything here.

### World fetch timeout - same root cause as the camera
`fetch_world_from_service` timed out after 300 s against a service that *is*
advertised and *is* answering. Measured: with nothing subscribed the link carries
zero IP fragment traffic; during one `ros2 service call` on
`/semantic_digital_twin/fetch_world`, 375,918 fragments arrived, 21 datagrams
reassembled, 374,828 failed (99.99%). `UdpRcvbufErrors` stayed at zero, so it is
not the socket buffer - it is the kernel's IP reassembly cache
(`ipfrag_high_thresh` 4 MB, `ipfrag_time` 30 s) thrashing under a retransmit
storm while nothing ever completes.

`FetchWorldServer` sends the whole world as one JSON string in a
`std_srvs/Trigger` response, with no chunking and no compression - measured at
about 30 MB - so it is a single very large sample, the same shape of payload that
killed the raw camera stream.

Fixed by raising the receiver's reassembly limits (`ipfrag_high_thresh` to 256 MB,
`ipfrag_time` to 3 s, `rmem` to 64 MB, `netdev_max_backlog` to 30000). The same
call now returns in 11 s with 720 datagrams reassembled against 2,785 failures,
where before it never returned at all. `python -m
experiments.montessori.perception.node --show-images` then runs end to end,
reporting 6 pieces and 6 holes once a second.

Applied at runtime only: writing `/etc/sysctl.d/60-ros2-large-messages.conf` was
blocked by the permission classifier, so the file is prepared in the session
scratchpad and the user has to install it for the tuning to survive a reboot.

Worth remembering: this is one root cause behind two symptoms. Anything on this
setup that sends a multi-megabyte sample over wifi will fail the same way, and
the general cure is a Fast DDS `maxMessageSize` below the MTU on the *sending*
side, which the robot would have to set.

### Network check and detection overlay (commit `241b3239b`)
`experiments/network_limits.py` reads the interface the default route leaves over
and, only when it is wireless, refuses to start with the exact `sysctl` command
if the limits are too low. The wired PC is untouched. Wired into both
`montessori_demo.main` and the perception node's `main`. The requirements are
declared once and the remedy command is generated from them, so the check and
the command cannot drift.

`perception/overlay.py` draws each detection's box, centre and name onto the
frame the viewer shows, reusing `OrthophotoProjector.pixel_T_region` rather than
writing new projection maths. `detections.py` gained `surface_height` - a piece's
pose stands half its height above the surface, everything else lies in its plane -
so the outline is projected onto the plane it was actually measured on.
`perception/colors.py` now holds the palette that `markers.py` had privately, so
rviz and the camera window agree.

Verified live: box, centre dot and label land on the real pieces, holes and
board. The box marks the footprint, so a piece's top face and shadow fall
outside it - that is the parallax the pipeline deliberately cancels, not an
error. 103 tests pass across the montessori and network files.

Watch out: `scripts/format_docstrings.py` damaged unrelated docstrings in
`montessori_demo.py` (split an `:attr:` reference across a blank line, and broke
another mid-identifier). Those hunks were reverted and the two needed lines
re-applied by hand. Check the diff after running it on a file you are only
touching lightly.

### Body boxes, the rectified window, and the depth's real limit (commit `318e8f322`)
The drawn box covered only the footprint, so a piece's top face fell outside it.
`MontessoriDetection.top_height` now names a detection's own top, and the overlay
boxes the outline drawn at both the resting surface and that top - exactly the
silhouette an upright prism casts, so the box covers the piece by construction.

That needed a height, and **the depth image on this table has none to give**.
Measured on a real frame: the piece tops read *further* than the table beside
them (rect prism top 0.961 m vs table 0.951 m; cube top 0.959 vs table 0.938),
so every piece came out zero tall. The board's 80 mm lid does resolve (0.988 vs
1.051), so it is a resolution limit on 30 mm objects, not a broken stream. The
depth-derived table plane fits `z = -0.039x - 0.005y + 0.905` with a 9 mm
residual - tilted about 2 degrees against the world horizontal.

So `_measure_height` now falls back to `LoosePieceDetector.piece_height`, the
same 0.03 it already assumes to cancel the parallax, whenever depth cannot
answer. A piece's pose then sits at table + 15 mm, which is exactly where the
Tracy demo rests the same piece (`table_top_z + CUBE_EDGE/2` = 0.895).

Viewer gained a third window, the rectified table with the detections on it.
`scale_to_fit` takes a height bound too, since that view is portrait (1000x1200
px at 1 mm, drawn 450x540). One `DetectionOverlay` serves both windows through
a `DetectionView` (`CameraView`, `RectifiedView`); `_on_color` no longer flashes
the bare frame before the annotated one.

### Position check against the Tracy demo (asked for, done)
Compared on a real captured frame. The only ground truth independent of where
things physically stand is the board's own hole layout, taken relative to the
detected board centre:

    cylinder   modelled (-0.022,-0.087)  detected (-0.017,-0.080)   8.2 mm
    cylinder   modelled (-0.017,+0.091)  detected (-0.012,+0.082)  10.8 mm
    cube       modelled (+0.020,-0.087)  detected (+0.017,-0.081)   6.8 mm
    triangle   modelled (+0.013,-0.000)  detected (+0.011,-0.001)   1.6 mm
    rectangle  modelled (-0.027,+0.000)  detected (-0.021,+0.001)   6.0 mm
    disk       modelled (+0.025,+0.091)  detected (+0.022,+0.079)  12.6 mm

Mean 7.7 mm, worst 12.6 mm; the residual is a systematic ~9% shrink of the
detected layout, not a shift. Not a plane-height error - undoing it would need a
lid *below* the table. Left unexplained.

Board and pieces do **not** stand where the demo's hardcoded layout puts them:
board detected at (0.804, 0.105) against `BOARD_POSITION_TRACY` (0.85, 0.0); the
piece row runs along x ~0.575 spaced 0.10 in y, against `SHAPE_ROW_X` 0.55 and
`SHAPE_ROW_SPACING` 0.15. The scene has simply been re-laid out since; z now
agrees exactly.

### Why every loose piece reads `cylinder` - diagnosed, not fixed
Root cause found, and it is the segmentation, not the classifier. The brushed
steel table throws a **diffuse coloured reflection** of each piece toward the
camera nadir, and `SurfaceColors.surface_mask` keeps it: measured on the yellow
rectangular prism, body saturation 100-145 / value 150-235, its halo 30-60 /
100-140, bare table 15-22 / 90-99. The halo of a saturated piece overlaps the
*body* of a pale one (cube body reads 33-64), so no global saturation floor
separates them. The specular highlight also washes the lit face of the pale
cyan pieces out to near-white, which the saturation floor then drops.

Consequences on a real frame (truth in brackets): rect prism 52x53 mm [20x40],
triangle 40x57 [37x32], cube 32x33 [30x30], cylinder 22x30 [28x28]. Even the
geometrically-good cube fills only 0.81 of its enclosing rectangle, under
`CrossSectionClassifier.circle_fill_ratio` 0.87, so it reads as a circle.

Tried and rejected: every combination of saturation floor 45/60/80 with value
floor 60/120/140/160 (best, 45/140, still misses the cube); Otsu on saturation
or value within each blob (over-erodes the pale pieces); and a three-plane
silhouette agreement adding the mirror plane at `table - piece_height`, which is
exact for a *sharp* reflection but the real one is a diffuse streak far larger
than the 11 mm mirror displacement. A real fix means changing how the pieces are
segmented; not attempted without agreeing it first.

### Piece matching, colour and orientation (commit `4824cc757`)
`experiments/montessori/pieces.py` now holds the physical set: measured dimensions
(moved out of `tracy_experiments/montessori/world.py`, which imports them back),
each piece's cross-section outline, its measured hue, and its rotation period.
`perception/piece_matcher.py` lays each known piece over the measured outline and
turns it through one period, scoring by intersection over union; the best fit
gives shape, yaw and confidence together. Holes keep the old
`CrossSectionClassifier` - they read correctly.

Yaw is the *smallest* turn reaching the observed pose (cube at 80 deg reports
-10; cylinder reports 0). `MontessoriDetection.yaw` and
`MontessoriShapeDetection.outline_overlap` expose it; `report()` logs both.

`SurfaceColors.piece_mask` segments by *wearing a piece colour* rather than by
standing out from the surface. This was forced by the user laying paper towels
down mid-session: the mat reads hue 42 / saturation 45, right at
`minimum_saturation`, so it passed as one 481 cm2 object and swallowed the
pieces (1 of 4 found). With the hue gate the mat is excluded outright.
`minimum_hue_saturation` (30) is separate from `minimum_saturation` (45) because
the hue gate lets the saturation floor drop, and the pale cyan pieces wash out
towards white where they catch the light. Do not raise it back - at 45 the
cylinder is lost.

Measured hues (median over each blob's coloured pixels, as the pipeline reads
them): cube 86, cylinder 86, rect prism 22, tri prism 23, beige disk 28, white
ball 27, paper mat 42, board lid 20, bare steel saturation 12-20 (colourless).
So `HUE_TOLERANCE = 4` separates pieces (within 2) from clutter (6-7 away). The
board lid at 20 is inside the yellow window but is excluded by `board.encloses`.

Results. Clean render: 4/4 categories, yaw within 3 deg, overlap 0.94-0.97. Bare
steel, real frame: 2/4 correct (cube 0.85, cylinder 0.66), 0 wrong, 2 refused -
the yellow pieces are still swallowed by their own reflection. Was 0/4 before.
`minimum_overlap = 0.6` sits above the widest wrong-shape fit measured (0.52)
and below a piece read through its reflection (0.66).

### Point cloud + plane fit + clustering - tried, does not work here
The user asked whether PCL-style plane segmentation and euclidean clustering
would separate the pieces. Ran it (open3d 0.19 is installed) on live frames.

Bare steel: 693k points, RANSAC plane holds only 34% of them, table points
scatter +/-17 mm about the fitted plane. Clustering above the plane at 5/10/15 mm
clearance gives 12-20 clusters, but they are sheets of noise - cluster spans of
622x367x273 mm and 759x626x239 mm. None of the four pieces appears. Probing a
20 mm column of cloud directly over each piece: z medians 18.5, 7.1, 8.4 and 0.4
mm *below* the modelled table, with per-piece spreads of 22-31 mm. The pieces do
not stand out of this cloud at all.

With the mat: markedly better - plane inliers 34% -> 69%, scatter 17 -> 12 mm.
Correcting for the fitted plane's own tilt (dz/dx = -0.223), the cube reads 33 mm
and the triangle 25 mm above the local surface (true 30), but the rect prism
reads 11 and the cylinder 3.5. Clustering still fails to isolate them. So the
mat roughly halves the problem but does not solve it.

Conclusion: the method is the textbook one and is not the issue; this sensor
cannot see 30 mm objects on this table. A stereo depth camera on a mirror either
drops out or matches the reflection, which lands *behind* the surface - which is
exactly the negative heights above. Scripts: `point_cloud_trial.py`.

### Edge fitting on the bare table (commit `4b74460f8`)
The mat is gone for good - the user asked for the software fix instead. A piece is
now recognised by fitting the known pieces to the *edges* of the view rectified
onto the plane a piece's top face stands on, where that face lies at exactly the
piece's own footprint, undistorted and sharply bounded. The reflection has no
sharp boundary anywhere, so it no longer decides anything.

- `perception/edges.py`: `EdgeDistances` - Canny (30/90 on a 3px-blurred grey)
  plus a distance transform, in metres, with `agreement(outline, reach)` scoring
  the share of an outline lying within `reach` of an edge.
- `piece_matcher.py` rewritten: `match(edges, seed, hue)` walks and turns each
  hue-admissible piece over the view, coarse (3 mm / 6 deg, reach 8 mm) then fine
  (1 mm / 2 deg, reach 3 mm). `MatchedPiece` now carries `center`, so the fit also
  settles *where* the piece is. `minimum_agreement = 0.62`.
- `pipeline.py`: pose and outline come from the fit; a contour touching the edge
  of the region is passed over as only partly seen.
- `detections.py`: `outline_overlap` -> `outline_agreement`.
- Renderer: a piece's lit top face over its shaded sides (`PIECE_SIDE_BRIGHTNESS`
  150), and `reflection_spread`, a piece-coloured smear with no edge, tuned so the
  rendered outlines inflate exactly as the real ones do (15 mm -> 45x53 for a
  30 mm piece, against 47x51 measured).

Measured, bare steel (`frame.npz`): 4/4 correct, 0 wrong, agreements 0.69-0.86,
where the area fit managed 2/4. Positions move 4-13 mm onto the piece itself.
With the mat (`frame2`) 3/3 of what segmentation finds. With a hand in the shot
(`frame3`) 3/4 - the piece the hand touches misreads. 0.29-0.35 s per frame all
in, against 2.4-3.2 s for the brute-force search the coarse pass replaced.

Watch out: a perfectly placed fit scores ~0.79-0.89, not ~1, because a Canny edge
in a 1 mm picture sits about a pixel off the line that drew it. The threshold is
relative to that, so raising the resolution would need it re-measured.

Also gone: a beige jar at the table's far edge that was fitting a triangular
prism at 0.74. Its blob runs off the region boundary, and the new rule refuses
anything only partly in view. That rule separates it from every real piece in all
three captured frames.

### The view is cut down to the workspace (commit `1a1d578c4`)
`WorkspaceBox` (region + `minimum_height` / `maximum_height`) projects its eight
corners into the camera and `clip()` crops a colour or depth image to their hull,
blacking out the rest; `RgbdFrame.project` is the world-to-pixel it needs.
`MontessoriPerceptionPipeline.headroom` (0.15) sets the ceiling and `workspace`
builds the box. The node's colour *and* depth windows now show it - and the bare
unclipped images only while the camera cannot be placed in the world, which also
fixed a flash of the bare depth image on every frame.

Note the box is bigger than the table region at the table plane, on purpose: the
hull covers the region at both heights, so something tall standing at the edge of
the region is still shown whole.

### Where this work continues: the `knowledge-directed-perception` plan

Created 2026-08-28. `tracy_icra` is not one of its item branches, so
`session-start.sh` will not auto-discover it from this branch - this pointer is
how a session working here finds it.

- Manifest: `.claude/personal/plans/knowledge-directed-perception/plan.yaml` on
  `claude/personal-notes` (9 items, 3 waves).
- Dashboard: https://claude.ai/code/artifact/f53db2a5-babc-4316-a0d8-8961e7759aaa
- Tracking issue: cram2 fork #201.

Its first item, `montessori-perception-on-main`, lands
`experiments/src/experiments/montessori/perception/` on `main` off this branch -
sorinar329's `75258debd` plus the seven commits after it, and nothing else from
`tracy_icra`. Everything below stays true of this branch; the plan is where the
next round of work is tracked, not here.

### Next / open
- The x/y bounds of `TRACY_WORKSPACE` (x 0.35-1.35, y -0.45..0.75) still reach
  past the pieces and take in the clutter at the table's far edge (a jar, a spray
  bottle, a beige disk, all at y < -0.1). Tightening them is the user's call - the
  numbers describe their table, not ours.
- The pale cyan pieces are under-segmented on the mat (cube read 18x29 mm for a
  30x30, cylinder missed). Their lit faces wash out towards white. Colour only
  seeds the fit now, so this costs a piece only when it seeds nothing at all.
- The *hole* classifier degraded in the later lighting (frame3 read five of six
  holes as triangular_prism). Untouched by this work - it uses the old
  threshold-based `CrossSectionClassifier`. Worth pointing the same fit at it.
- `decode_color_image` and `decode_depth_image` (the raw-message decoders) now
  have no production caller and are only used by tests. AGENTS.md says to consult
  the developer before removing them - waiting on that decision.
- A depth reading of +1 mm still counts as measured, so the white ball on the
  table is reported 14 mm lower than a nominal piece. A noise floor would be a
  tuned number, so it was left alone.
- Scratchpad measurements for this round: `blobs.py`, `sweep.py`, `coarse.py`,
  `engine.py` / `engine2.py`, `chamfer_show.py`, `edges_look.py`, `final_check.py`
  against `frame.npz` (bare steel), `frame2.npz` (mat), `frame3.npz` (hand in
  shot); recapture with `capture_frame.py` if the scene moves.
- No pull request opened. This work folds into `tracy_icra`, which already
  carries a colleague's commits and tracks their fork, so a PR for it would be
  proposing their work too. Left for the user to decide.

## Merge with `main`, 2026-08-28 (`demo-catches-up-with-main`)

Plan item `demo-catches-up-with-main` of `knowledge-directed-perception`. The
plan's reasoning is in that plan's `roadmap.md`; this is the branch-level log.

Merged `origin/main` into `tracy_icra` — 277 commits since the 2026-08-19 merge
base `1646dd355`, against the 234 the plan recorded four days earlier.

### Done
- `fb0d0e41` — the merge. One conflict, in `multi_sim.py`, eight hunks, both
  sides having reworked the same MuJoCo sync. Resolved as a union: `main`'s
  extracted `_read_connections_from_qpos` / `_write_connections_to_qpos` under
  `_world_lock` (which subsumes this branch's inline `_model_lock` loops), with
  this branch's `renderer.lock()` carried into both helpers and every
  `physically_simulated_dofs` behaviour kept in full.
- `ece5eb74` — three call sites in branch-only files that `main` had broken
  without conflicting, because `main` never had those files:
  `with_tf_publisher()` (removed), `translate_free_space_to_where_condition` and
  `navigation_map_at_target` (moved onto `PlanarGraphOfBoundingBoxes`), and a
  `Point3` passed to a planar graph's `Point2`-bound `node_of_point`.
- The merge drops the `ormatic_interface.py` files this branch still tracked.
  `main` already ignores them, which is what `AGENTS.md` requires.

### Next
- The three wave-1 perception items stack on this: `surfaces-from-world`,
  `detect-per-supporting-surface`, `one-detection-per-thing`.
- `montessori-perception-on-main` still has to cut the perception package off
  `main` as its own reviewable branch. Untouched by this merge, which
  deliberately left `tracy_icra` where it is rather than rewriting it.

### Watch out for
- The `multi_sim.py` sync path is threading code whose failure mode is a lost
  write under contention. No unit test in that module exercises it; the merge is
  only really proven by the demo running on the real robot.
- The branch's upstream still points at `sorin/tracy_icra`. This merge went to
  `origin`, as the earlier rounds did.

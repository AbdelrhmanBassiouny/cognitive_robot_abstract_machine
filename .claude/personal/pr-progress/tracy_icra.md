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

### Next / open
- `decode_color_image` and `decode_depth_image` (the raw-message decoders) now
  have no production caller and are only used by tests. AGENTS.md says to consult
  the developer before removing them - waiting on that decision.
- The piece segmentation above. The measurements are in the scratchpad scripts
  (`segment_trials.py`, `three_plane.py`, `compare_demo.py`) against a captured
  frame; recapture with `capture_frame.py` if the scene moves.
- A depth reading of +1 mm still counts as measured, so the white ball on the
  table is reported 14 mm lower than a nominal piece. A noise floor would be a
  tuned number, so it was left alone.
- No pull request opened. This work folds into `tracy_icra`, which already
  carries a colleague's commits and tracks their fork, so a PR for it would be
  proposing their work too. Left for the user to decide.

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

### Next / open
- `decode_color_image` and `decode_depth_image` (the raw-message decoders) now
  have no production caller and are only used by tests. AGENTS.md says to consult
  the developer before removing them - waiting on that decision.
- The pipeline labels every loose piece `cylinder` on the real table, including
  the cube and the triangular prism, while the board's holes come out right. The
  overlay makes this plainly visible now. Not investigated - it is the
  classifier's behaviour on real data, not anything from this work.
- No pull request opened. This work folds into `tracy_icra`, which already
  carries a colleague's commits and tracks their fork, so a PR for it would be
  proposing their work too. Left for the user to decide.

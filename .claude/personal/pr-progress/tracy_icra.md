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

### Next / open
- `decode_color_image` and `decode_depth_image` (the raw-message decoders) now
  have no production caller and are only used by tests. AGENTS.md says to consult
  the developer before removing them - waiting on that decision.
- No pull request opened. This work folds into `tracy_icra`, which already
  carries a colleague's commits and tracks their fork, so a PR for it would be
  proposing their work too. Left for the user to decide.

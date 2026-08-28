## Branch `tracy_icra` - Montessori perception over the wifi link

### Plan
Make the continuous Montessori perception node actually receive camera data from
the real camera over the robot's wifi network.

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
- `camera.py`: added `ImageTransport`, `CompressedImageFormat` (parses the
  `format` field), `DepthQuantization` (the `compressedDepth` header), and
  `decode_compressed_color_image` / `decode_compressed_depth_image`.
- `exceptions.py`: added `UndecodableCompressedImage`.
- `node.py`: `CameraTopic` now names `/camera/color/image_raw/compressed` and
  `/camera/depth/image_raw/compressedDepth`; subscriptions take `CompressedImage`.
- Tests: 8 new decoder tests written before the implementation; 35 pass in
  `test_montessori_perception.py`, 75 across the montessori files.
- Verified live against the real camera through the node's own code path: colour
  (1080, 1920, 3) uint8, depth (1080, 1920) float32 spanning 0.79-2.47 m, and the
  two registered onto each other.

Measured transports on this camera: colour compressed 18.9 Hz / 3.83 MB/s;
`compressedDepth` PNG ~118 kB per frame. `/camera/depth/image_raw/compressed` is
JPEG-mono8 and publishes a 0-byte payload, so it is not usable for depth.

### Next / open
- `decode_color_image` and `decode_depth_image` (the raw-message decoders) now
  have no production caller and are only used by tests. AGENTS.md says to consult
  the developer before removing them - waiting on that decision.
- Nothing committed yet; these changes sit in the working tree on `tracy_icra`
  alongside pre-existing unrelated modifications.
- Pre-existing and unrelated: `test/experiments_test/` fails to collect as a
  whole because `json_msgs` is not installed. Reproduced with these changes
  stashed, so it is not from this work.

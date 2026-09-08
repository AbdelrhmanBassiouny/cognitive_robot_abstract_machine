
## icra-foundation / simulated-camera-feeds-perception — PR #298 (draft)

Branch `claude/simulated-camera-feeds-perception-iba2oa`, cut off #265
(`claude/icra-experiments-simulation-pipeline-w4ep7n`), which is where the perception
pipeline a frame gets fed to exists. Item recorded `in_progress`; the settled plan and its
reasoning are in `icra-foundation/roadmap.md`'s own section for this item.

### The plan

Render an `RgbdFrame` out of the twin, so every reader of that type works in simulation. Four
conversions are the whole of it — intrinsics from the MuJoCo camera's field of view, MuJoCo's
far-plane depth to the frame's zero-means-no-reading, RGB to OpenCV BGR, and the MuJoCo camera
frame to the optical one (a half turn about x).

1. `test/experiments_test/test_montessori_simulated_camera.py` first, per TDD — one test per
   conversion, each asserted against the definition (the render itself, `WorkspaceSurface`'s
   stated lid height, `KnownPiece.color`), plus the item's own criterion: a scene with the
   board and four pieces reports every piece once with the right category.
2. `experiments/montessori/perception/simulated_camera.py` — `SimulatedCamera`, the fourth
   producer of `RgbdFrame` beside a capture, a rosbag and the live ROS node. Mirrors
   `MujocoVideoRecorder`'s headless-mirror lifecycle (`start`/`stop`, `MUJOCO_GL=egl`,
   `mj_forward` before each render).
3. `CameraIntrinsics.of_field_of_view` on `perception/camera.py`, beside the
   `from_camera_info_matrix` that already reads the other way in.
4. `experiments/montessori/perception/simulated_setup.py` — the simulated rig: the pipeline
   over a `MontessoriWorld`'s own surfaces, read through `WorkspaceSurface.of` rather than
   restated the way `recorded_setup.py` has to restate the real one.
5. `generate_orm.py`'s ignore list gains the new modules, same reason and same region as #261,
   #278, #294 and #296.

### Done

- Branch cut, pushed, draft PR #298 opened against #265.
- Manifest: `branch`, `pull_request_number`, `session`, `status: in_progress`; roadmap section
  appended.
- Research recorded in the roadmap section rather than only here: no vision-language or VQA
  backend exists in the workspace (`icra-mechanism` owns both), the measured colours and
  finishes are already on `MontessoriWorld`, and `capture_rgb`/`capture_depth` already exist
  on `MujocoSimulator`.

### Next

- Write the tests, then the modules, in the order above.
- Two things only a real run can settle: whether offscreen MuJoCo rendering gets an EGL
  context in a session container, and whether the detectors actually find four rendered pieces.
  The second is the item's own done-criterion and is the one that can legitimately come out
  red; report the measurement, do not weaken the test.

### Standing

- Re-draft PR #298 after every push. Never subscribe to it. No scheduled check-ins.
- Tracking-issue #252 subscription was refused by the permission classifier this session, so
  structural changes to the plan will not arrive as events here.


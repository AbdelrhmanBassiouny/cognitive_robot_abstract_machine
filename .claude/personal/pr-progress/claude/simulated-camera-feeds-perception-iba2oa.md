
## icra-foundation / simulated-camera-feeds-perception — PR #298 (draft)

Branch `claude/simulated-camera-feeds-perception-iba2oa`, cut off #265
(`claude/icra-experiments-simulation-pipeline-w4ep7n`), which is where the perception
pipeline a frame gets fed to exists. Item `in_progress`. The plan, the measurements and
the findings are in `icra-foundation/roadmap.md`'s sections for this item; the pull
request description carries the same.

### Done — the work is complete and pushed

Five commits on top of the bootstrap. The first three are the frame source:

1. `select_offscreen_rendering_backend` shared between the video recorder and the new
   camera, backends a `StrEnum`, `MUJOCO_GL` named once.
2. `CameraIntrinsics.of_field_of_view`, beside the matrix reader that already existed.
3. `simulated_camera.py` + `simulated_setup.py` + the tests, and both new modules added
   to `generate_orm.py`'s ignore list.

The last two answer the first review round (*"make them transparent regions and make it a
toggelable thing"*), rebased onto the branch's merge of its base:

4. `d2978798cf` — `RegionAppearance` on `MultiSimBuilder`: `TRANSPARENT` (0.3 of the
   opacity the region itself states) everywhere a world is built or a region spawned, or
   `HIDDEN`, which builds the region's body and none of its geometry. The share is
   applied where a shape becomes a geom, so the builder and the runtime spawner agree.
   `MujocoSim(region_appearance=...)` is the toggle.
5. `9cb2844bdc` — `SimulatedCamera` hides them, because the real camera sees no volume of
   space, with the two detection tests marked expected-to-fail and why.

Green in the container: 12 passed / 2 xfailed (simulated camera), 4 passed (region
appearance), 4 passed (backend choice), 16 passed (video recorder, `CI=true`). The
adapter suite runs 3 failed / 147 passed / 11 errors against the base's 3 / 143 / 11 —
same failures, all `test_urdf`/`test_gazebo` container artefacts, plus my four. The three
`test_experiments` failures (`test_free_space_volume_estimation`, two
`test_montessori_perception_backend`) fail identically on `2b2b23a81a`, checked in a
worktree.

### Three things for the developer, all reported and none fixed here

- **Which default should the camera use?** It hides regions now; drawing them see-through
  is the only setting where the board is found, and only because the markers give its
  holes an outline. One word either way.
- **Which piece size is the real one?** The twin builds its shapes from the board's own
  holes and `pieces.py` measured its outlines off the captures, and the two disagree by
  25–32 % (cube 22.4 mm against 30, cylinder 22.4 against 28, triangular prism 25.2 by
  29.4 against 37 by 32, rectangular prism 15.4 by 29.4 against 20 by 40). That is why
  the cube's place is won by the cylinder's outline, and why both detection tests xfail.
- **`SceneToSearch.expected_pieces` raises `KeyError`** on a world holding a shape
  perception knows no piece for — a disk or a sphere, which `MontessoriWorld` spawns. A
  defect of the merged tree; one root cause per branch, so it wants its own bug PR.

### Standing

- Re-draft PR #298 after every push (it is a draft now). Never subscribe to it. No
  scheduled check-ins.
- The review thread on the xfail is answered and left **open**: it asks the developer the
  first two questions above.
- Tracking-issue #252 subscription was refused by the permission classifier, so
  structural plan changes will not arrive as events here.
- Container recipe, if a later session needs it: Python **3.12** (3.11 fails first on
  `dataclasses.make_dataclass(module=)`), workspace sources on `PYTHONPATH` minus
  `probabilistic_model/src`, the `random_events` wheel for its compiled library, stubs
  for `xacro` and `giskardpy_bullet_bindings`, `apt install libegl-mesa0`, and
  `CRAM_ORM_BUILD=never` so the conftest does not try an ORM build that needs ROS. Two
  pytest runs at once collide on `/tmp/scene.xml`, which is what a run of unexplained
  extra failures turned out to be.


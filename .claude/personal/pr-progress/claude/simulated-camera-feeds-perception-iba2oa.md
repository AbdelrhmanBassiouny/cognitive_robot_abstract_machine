
## icra-foundation / simulated-camera-feeds-perception — PR #298 (draft)

Branch `claude/simulated-camera-feeds-perception-iba2oa`, cut off #265
(`claude/icra-experiments-simulation-pipeline-w4ep7n`), which is where the perception
pipeline a frame gets fed to exists. Item `in_progress`. The plan, the measurements and
the two findings are in `icra-foundation/roadmap.md`'s sections for this item; the pull
request description carries the same.

### Done — the work is complete and pushed

Three commits on top of the bootstrap:

1. `select_offscreen_rendering_backend` shared between the video recorder and the new
   camera, backends a `StrEnum`, `MUJOCO_GL` named once.
2. `CameraIntrinsics.of_field_of_view`, beside the matrix reader that already existed.
3. `simulated_camera.py` + `simulated_setup.py` + the tests, and both new modules added
   to `generate_orm.py`'s ignore list.

Green: 11 passed / 1 xfailed (simulated camera), 4 passed (backend choice), 16 passed
(video recorder, with `CI=true`, which is what actually exercises the extraction).

### Two things for the developer, both reported and neither fixed here

- **Should a `Region` be rendered into a picture at all?** It is exported to MuJoCo as a
  visible geom, so the board's six hole regions render as solid markers wearing the piece
  detectors' own hues. That is why the item's stated criterion is xfailed (strictly): the
  extra reports and the unfound board are both this one cause. Fixing it is one flag at
  the region conversion site but changes what every viewer and every recorded video
  shows, so it is his call.
- **`SceneToSearch.expected_pieces` raises `KeyError`** on a world holding a shape
  perception knows no piece for — a disk or a sphere, which `MontessoriWorld` spawns. A
  defect of the merged tree; one root cause per branch, so it wants its own bug PR.

### Standing

- Re-draft PR #298 after every push (it is a draft now). Never subscribe to it. No
  scheduled check-ins.
- Tracking-issue #252 subscription was refused by the permission classifier this session,
  so structural plan changes will not arrive as events here.
- Container recipe, if a later session needs it: Python **3.12** (3.11 fails first on
  `dataclasses.make_dataclass(module=)`), workspace sources on `PYTHONPATH` minus
  `probabilistic_model/src`, the `random_events` wheel for its compiled library, stubs
  for `xacro` and `giskardpy_bullet_bindings`, `apt install libegl-mesa0`, and
  `CRAM_ORM_BUILD=never` so the conftest does not try an ORM build that needs ROS.


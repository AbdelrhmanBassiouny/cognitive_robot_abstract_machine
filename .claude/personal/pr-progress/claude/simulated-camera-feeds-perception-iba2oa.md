## icra-foundation / simulated-camera-feeds-perception — PR #298 (draft)

Branch `claude/simulated-camera-feeds-perception-iba2oa`, cut off #265
(`claude/icra-experiments-simulation-pipeline-w4ep7n`). Item `in_progress`. The plan, the
measurements and the findings are in `icra-foundation/roadmap.md`'s two review-round
sections for this item; the pull request description carries the same.

### Done — two review rounds handled, everything pushed and green where it can be

The frame source is three commits (shared backend choice, `CameraIntrinsics.of_field_of_view`,
`simulated_camera.py` + `simulated_setup.py` + tests). On top of it:

1. `d2978798cf` / `9cb2844bdc` — round one: `RegionAppearance` on `MultiSimBuilder`
   (`TRANSPARENT` by default, `HIDDEN` builds the body and no geometry),
   `MujocoSim(region_appearance=...)` the toggle, `SimulatedCamera` hiding them.
2. `b39c7e3ead` — the base's merge, which brings its `RecordedLook` fix and so clears 9
   failures and 14 errors of the experiments job that were never this branch's.
3. `9d4aa50edb` — round two: a loose piece is built the size `KnownPiece` states, not 0.7
   of its hole. Cube 30.0, both cylinders 28.0, rectangular prism 21.0 × 40.0, triangular
   prism 31.7 × 37.0, all 30.0 tall. One scale for both axes, so a piece keeps its hole's
   orientation and can still be released unrotated.
4. `4188e257ce` — the `experiments` CI job exports `MUJOCO_GL=egl`; that was the whole of
   the `gladLoadGL` failure, reproduced locally and fixed by the export.
5. `b258926338` — both expected-to-fail marks renamed onto the real cause.

Verified in the container (Python 3.12, `MUJOCO_GL=egl`, `CRAM_ORM_BUILD=never`):
simulated camera 12 passed / 2 xfailed, world 25 passed / 1 skipped, region appearance 4,
rendering backend 4. `test/experiments_test` runs 707 passed / 4 failed, and all four
reproduce on `b39c7e3ead` in a worktree.

Both review threads are answered and **resolved** — the asks were done as asked.

### Three things for the developer, all reported and none taken here

- **A sorting run.** Clearance goes from 0.70 everywhere to 0.70–0.95, tightest on the
  rectangular prism at ~1 mm a side. The 0.7 was tuned against insertion pass rates over
  20 runs; nothing in a session container can run one.
- **`Occupancy` annihilates agreement.** With the pieces at their measured sizes both
  detectors find all four within a millimetre, and `keep_one_detection_per_place` drops
  *both* readings of every place they agree on inside `required_lead`. Only the cylinder
  survives. The same detectors disagree enough on the real captures, so a noiseless
  picture is what shows it. Wants its own branch in `occupancy.py`.
- **`SceneToSearch.expected_pieces` raises `KeyError`** on a world holding a shape
  perception knows no piece for. Still open, still its own bug PR.

### Standing

- Re-draft #298 after every push (it is a draft now). Never subscribe to it. No scheduled
  check-ins. Do not open a bug PR for the two defects above without being asked.
- `select_offscreen_rendering_backend()` cannot reach either of its callers — MuJoCo fixes
  its backend at import. That is `main`'s shape, left alone beyond a warning in the
  docstring; only the environment a run starts from chooses the backend.
- Container recipe: Python **3.12** venv, workspace sources on `PYTHONPATH`, `mujoco`,
  `casadi~=3.7.0`, opencv, trimesh, `usd-core`, rtree, scikit-image, the
  `random_events`/`probabilistic_model` wheels, `apt install libegl-mesa0`, and stubs for
  `xacro` and `giskardpy_bullet_bindings`. **The bullet stub needs arithmetic and iteration
  dunders**, not just `__getattr__`, or `MontessoriWorld()` dies in the collision detector.
  `CRAM_ORM_BUILD=never` skips the conftest's ORM build. Export `MUJOCO_GL=egl` before
  pytest, never from inside it. Two pytest runs at once collide on `/tmp/scene.xml`.

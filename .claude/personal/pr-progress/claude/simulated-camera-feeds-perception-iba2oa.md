## icra-foundation / simulated-camera-feeds-perception — PR #298 (draft)

Branch `claude/simulated-camera-feeds-perception-iba2oa`, cut off #265
(`claude/icra-experiments-simulation-pipeline-w4ep7n`). Item `in_progress`. The plan, the
measurements and the findings are in `icra-foundation/roadmap.md`'s three review-round
sections for this item; the pull request description carries the same.

### Done — three review rounds handled, everything pushed, the item's own criterion passing

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
6. `8fc06067ce` — the base merged in again (its `unfinished_motions` rename), by another
   session; taken as a fast-forward.
7. `6c968260eb` — round three, first half: an opening is read from the depth as well as
   from the darkness. `RgbdFrame.measured_height`, `Orthophoto.measured_height` and
   `Orthophoto.opening_mask` are new; `BoardDetector` sizes each reading on its own before
   the two are put together, and the rim of an opening the colours do not carry is handed
   to the fit as an edge (`EdgeDistances.of(..., together_with=...)`).
8. `15dfd354cd` — round three, second half: `Occupancy` reports the thing two ways of
   looking agree on rather than neither, and `OccupiedVolume` intersects its outlines in
   millimetres. Both expected-to-fail marks come off.

**The item's criterion passes**: all four pieces reported once each with their own
categories, within a millimetre of where the twin put them, and the board found with its
six holes, every hole on the hole of its own category (worst 5.4 mm, median 1.2 mm).

Verified in the container (Python 3.12, `MUJOCO_GL=egl`, `CRAM_ORM_BUILD=never`):
simulated camera 15 passed, captures 57 passed / 4 xfailed (unchanged), occupancy 24,
views 31, explanations 17, world 25 / 1 skipped, region appearance 4, rendering backend 4.
The whole of `test/experiments_test` this container collects runs 738 passed, 25 failed,
4 errors — every failure a database or generated-ORM one it has neither `psycopg` nor a
built interface for, apart from `test_free_space_volume_estimation` and the two
`test_montessori_perception_backend` narrowing tests, which fail identically with these
changes stashed.

All four review threads are answered and **resolved**.

### Three things for the developer, all reported and none taken here

- **A sorting run.** Clearance goes from 0.70 everywhere to 0.70–0.95, tightest on the
  rectangular prism at ~1 mm a side. The 0.7 was tuned against insertion pass rates over
  20 runs; nothing in a session container can run one.
- **The captures' own depth disagrees with the rig `recorded_setup` states.** The board's
  top surface measures at 0.879 where the lid is stated at 0.960 (the table's stated 0.880
  measures right), and a piece on the lid measures the same height as a piece on the table.
  So either those stated planes or the captures' extrinsics are wrong. Untouched: moving a
  stated plane moves every rectification in the package.
- **`SceneToSearch.expected_pieces` raises `KeyError`** on a world holding a shape
  perception knows no piece for. Still open, still its own bug PR.

### Standing

- Re-draft #298 after every push (it is a draft now). Never subscribe to it. No scheduled
  check-ins. Do not open a bug PR for the defect above without being asked.
- `select_offscreen_rendering_backend()` cannot reach either of its callers — MuJoCo fixes
  its backend at import. That is `main`'s shape, left alone beyond a warning in the
  docstring; only the environment a run starts from chooses the backend.
- The perception package exists on no ancestor reaching `main`, so a bug in it has no base
  for a PR of its own; `occupancy.py`'s two fixes landed here and the reply says so.
- Container recipe: Python **3.12** venv, workspace sources on `PYTHONPATH`, `mujoco`,
  `casadi~=3.7.0`, opencv, trimesh, `usd-core`, rtree, scikit-image, the
  `random_events`/`probabilistic_model` wheels, `apt install libegl-mesa0`, and stubs for
  `xacro` and `giskardpy_bullet_bindings`. **The bullet stub needs arithmetic and iteration
  dunders**, not just `__getattr__`, or `MontessoriWorld()` dies in the collision detector.
  `CRAM_ORM_BUILD=never` skips the conftest's ORM build. Export `MUJOCO_GL=egl` before
  pytest, never from inside it. Two pytest runs at once collide on `/tmp/scene.xml`. Seven
  test modules fail to collect at all (ROS/ORM imports) and need `--ignore`.
- The session-start hook rewrites `CLAUDE.local.md` on every resume, so edits to the
  manifest and roadmap blocks are lost unless `save-plan.sh` has already run. Save early.

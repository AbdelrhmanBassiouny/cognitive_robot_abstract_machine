## claude/insert-action-14xvqi — a coraplex insertion action, and the cube's place

Stacked on `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265); the draft PR
targets that branch.

### Plan
1. `Aperture.landing_region` moved up from `ShapeSortingHole` — done.
2. `coraplex/.../actions/core/insertion.py`: `InsertAction` (target is an `Aperture`,
   EQL pre/post conditions) — done, 7 tests green.
3. `InsertActionMujoco` beside `PlaceActionMujoco`; `MujocoSortingRig` drives it — done.
4. `PutThePieceInItsHole` / `SortingScene` insert rather than place — done, test added.
5. `InsertMontessoriShapeAction` thinned onto `InsertShapeAction(InsertAction)`, which
   asks the shape for its release pose — done, two tests added.
6. Cube starts on the board's lid, furthest from the square hole — done
   (`CUBE_STARTS_ON_THE_LID`, `experiments.montessori.world.solid_lid_away_from`).
7. Framework figure: cube on the lid, plan prints `InsertAction` — done, re-rendered.

### Merged with base
`origin/claude/icra-experiments-simulation-pipeline-w4ep7n` moved to `1bcef7d49`; merged
in at `f227cebbc`. One conflict, in `pickup_demo_mujoco.py`'s imports — both sides added
to adjacent lines (`solid_lid_away_from` here, `SceneAsSetUp` there); kept both.
`scenarios.py` and `world.py` auto-merged with both sides' additions intact.

### Outstanding
- Nothing runnable here exercises the MuJoCo Tracy path: this container has no
  `iai_tracy_description` matching the lab's (the public clone uses `robotiq_arg2f_*`
  where the lab's Tracy expects `robotiq_85_*`). `test_tracy_pickup_demo_mujoco.py`,
  `test_tracy_pick_and_place_action.py` and `test_tracy_montessori_*` are CI-only —
  watch them on the PR.
- Found, not fixed (separate PR): `InsertMontessoriShapeAction.target_horizontal_offset`
  is documented and set by `montessori_demo` but never read — the old `_action_plan`
  hardcoded a zero offset, and the change preserves that. Its test passes only because
  its tolerance (0.05) swallows the offset (0.01).

### Local environment (not committed)
- `pip install -U uv` then `uv sync --python /usr/bin/python3.12 --extra dev`.
- No ROS here: a `.pth` in `.venv` loads `rosstub.py` from the scratchpad, which
  fabricates the ROS packages and makes `get_package_share_directory` search
  `AMENT_PREFIX_PATH` on disk. ~92 coraplex tests and most experiments tests then run;
  the rest need real description packages.
- The framework figure renders with a throwaway venv holding `numpy<2` and
  `pyopengl @ git+https://github.com/mmatl/pyopengl.git` plus `libosmesa6`/`libglu1-mesa`,
  and the three description clones on `ROS_PACKAGE_PATH`. It reproduced the committed
  PNGs byte-for-byte before the change, so the diff is only the cube moving.

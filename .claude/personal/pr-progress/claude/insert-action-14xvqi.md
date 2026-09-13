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

### Review round 1 (2026-09-13, comment r3999689257 on `insert_shape_action.py`)
Proposal, not a defect: rather than a new action, EQL-based RDR rules (`EQLSingleClassRDR`)
that choose the target from context; and the figure's target hole filled by an RDR backend
from an underspecified statement.

Replied (r3999715839), **left open** — it forks into three and needs a decision:
- The figure already colours the `target=a(ShapeSortingHole)(...)` slot as the *rules*
  backend, but the code behind it is `ShapeSortingBoard.hole_for`, a hand-written
  three-tier lookup (fits_through filter, name pairing, smallest-fitting fallback).
  Making that an `EQLSingleClassRDR` is agreed and plugs in upstream of `InsertAction`
  (whose `target` is already a statement) — recommended as a follow-up PR, since
  `hole_for` is on the base branch with five callers including `event_monitoring`.
- Target-selection rules do not replace `InsertAction`: they choose *where*, not the
  post-condition (`InsideOf` the landing region) or the descent through the aperture.
- The design that would collapse the two actions is a polymorphic *target* (surface or
  aperture states its release pose and its satisfied condition), not an action subclass —
  which does sidestep the LSP objection raised earlier. Rewrite of this PR + `PlaceAction`.

Awaiting the choice between (a) rules as a follow-up, (b) rules in this PR, (c) collapse
into a polymorphic-target `PlaceAction`.

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

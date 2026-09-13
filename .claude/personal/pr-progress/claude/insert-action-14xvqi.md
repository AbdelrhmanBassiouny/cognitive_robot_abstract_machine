## claude/insert-action-14xvqi — a coraplex insertion action, and the cube's place

Stacked on `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265); the draft PR
targets that branch.

### Plan
1. `Aperture.landing_region` moved up from `ShapeSortingHole` — done.
2. `coraplex/.../actions/core/insertion.py`: `InsertAction` (target is an `Aperture`,
   EQL pre/post conditions) — done, 7 tests green.
3. `InsertActionMujoco` beside `PlaceActionMujoco`; `MujocoSortingRig` drives it — done.
4. `PutThePieceInItsHole` / `SortingScene` insert rather than place — done, test added.
5. `InsertMontessoriShapeAction` builds `InsertAction` directly, handing it the turn
   the shape states for its hole (`target_R_body`) — done, two tests added.
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

Replied (r3999715839) laying out three readings; the answer (r3999854266) was
"no `InsertShapeAction` is needed, only `InsertAction` is enough."

**Done at `d11d1ad6c0`.** `InsertShapeAction` existed for one thing: a disk has to be
tipped onto its edge for its slot. That is a property of the body, not a second kind of
insertion, so `InsertAction` carries
`target_R_body: RotationMatrix = field(default_factory=RotationMatrix, kw_only=True)`
(identity = turned the way the opening is), and `InsertMontessoriShapeAction` hands it
`insertion_pose_relative_to_hole(...).to_rotation_matrix()`. `DiskShape` keeps the
knowledge it already had. New coraplex test
`test_a_body_that_only_fits_turned_is_released_turned_that_way` (verified red before the
field existed); the two montessori release-pose tests build `InsertAction` directly.

`RotationMatrix` was chosen over a whole `Pose` field partly because it is what the sdt
style guide's `root_R_tip` notation names, and partly because it has an ORM
`AlternativeMapping` like `Pose` does, so it survives the `FeatureExtractor` the
`ProbabilisticBackend` runs over every `a(...)`-wrapped field.

**Thread left open** for the other half of the original comment: the RDR filling `target`
is still a follow-up PR (`hole_for` is on the base branch with five callers including
`event_monitoring`). Replied r3999968096 saying so.

### CI round 1 (13 failures on f227cebb) - both fixed
Two causes, both diagnosed from the `experiments` job log:

1. **5 in `test_montessori_insert_shape_action.py`** - `ValueError: Value cube not in
   domain of variable Symbolic(InsertShapeAction.target.shape_category, ∅)`. Not this
   PR's bug: `PolymorphicEnumType` maps back to the abstract `enum.Enum`, which has no
   members, so `FeatureExtractor._process_attributes` built an empty-domain variable for
   any entity with an enum field handed to a query the `ProbabilisticBackend` resolves.
   Fixed in its own bug PR off main: **#357**, branch
   `claude/polymorphic-enum-feature-domain-14xvqi`. Merged into this branch at
   `471a6ca3df` (one conflict, an import line in `example_classes.py`; kept both), so
   this stack no longer waits for #357 to land.

2. **8 in `test_tracy_pickup_demo_mujoco.py`** - this PR's. `PerceivedScene.perceive`
   stood only the pieces resting on the bare table, so the cube on the lid was never
   perceived and never sorted; everything downstream cascaded from that. Fixed at
   `3e9e5b069`. Whether the simulated MuJoCo camera actually detects the cube on the lid
   can only be answered by CI.

### Base merge 2 (2026-09-13)
`origin/claude/icra-experiments-simulation-pipeline-w4ep7n` moved to `62e046bf95` (film
written as taken, per-worker scene files, camera optical-frame offset). Merged at
`e7d1a2ebbf`; one conflict, two adjacent imports in `test_tracy_pickup_demo_mujoco.py`
(`CUBE_STARTS_ON_THE_LID` here, `CAMERA_VIDEO_RESOLUTION` there) - kept both.

### Local sweeps
- `test_insertion.py` + `test_montessori_insert_shape_action.py` +
  `test_montessori_scene_publishing.py`: 23 passed, 7 skipped (HSR).
- `test_montessori_scenarios.py` + `test_montessori_semantics.py` + publishing: 119
  passed; the 1 failure and 3 errors are all GLFW/`DISPLAY` (no X11 here).
- The Tracy/MuJoCo errors in a full sweep are all
  `PathResolutionError: iai_tracy_description` - the known environment gap, not the diff.
- krrood tests cannot share a pytest invocation with the others: its conftest regenerates
  its own dataset ORM and collides with the already-registered metadata
  (`InvalidRequestError: Table '_789...' is already defined`). Run them separately.

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

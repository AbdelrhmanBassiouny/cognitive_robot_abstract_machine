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

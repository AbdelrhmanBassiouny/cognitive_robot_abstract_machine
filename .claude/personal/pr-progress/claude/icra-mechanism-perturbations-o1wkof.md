# icra-mechanism / perturbations — PR #311 (on #265, CI being fixed)

Replaces #305. Branch `claude/icra-mechanism-perturbations-o1wkof` off #265, which is
where it is to be merged. Carries no `.claude/` tooling change — the reason #305 was closed.

## Done

- The perturbations themselves: `TargetHoleMoved`, `PieceShoved` (world);
  `PerturbationOfWhatIsSeen` + `PerturbationOfTheNextLook` marker + `PerceivedPoseOffset`,
  `DetectionRelabelled` (what a look reports); `LookAtTheScene` + `SortingStep.LOOK`;
  `Perturbation.instruction_for_a_person()` on the shared base. 25 new tests; 96 passed.
- Manifest recorded (`in_progress`, branch, PR, session); roadmap sections appended;
  dashboard at v12.

## In flight: the developer asked for the CI to be fixed

All nine failures were on the base (#265) at the identical commit — `experiments`,
`coraplex` and `semantic_digital_twin` fail the same way on #265's own run 34577080504.
Fixed here because this branch merges into #265.

- `RotationMatrix.rotational_error` -> `rotational_distance` (renamed on main); the
  numeric counterpart `NumericPose.rotational_error` renamed to match. 21 pass.
- Three stale renames breaking collection: `krrood.utils.clear_memoization_cache` ->
  `krrood.patterns.caching`, `_extrude_polygon` -> `extrude_polygon`,
  `AttachNode`/`DetachNode` -> `ReAttachNode`, `_HOLE_KEY_BY_CATEGORY` ->
  `HOLE_NAME_BY_CATEGORY` (ported from #301's `0e1754407`).
- `_landing_region_height`/`_landing_region_position` were folded into
  `_open_space_under`; `tracy_experiments`' and `world2`'s own landing-region passes
  rebuilt on the base class's `_give_every_hole_its_landing_region`, which now takes the
  two heights instead of reading module constants. #301 left this one unfixed.
- `confidence_aware_eql/data_generation.py`: `query.expression.limit(...)` never reached
  the query's own limit; `query.limit(...)` (ported from #301). 10 pass.
- Four giskardpy ROS2 middleware modules imported `json_msgs` at module level; deferred
  (ported from #301).
- `multi_sim.py`'s keyframe `ctrl` loop read `world.state[actuator.dofs[0].id]`, which a
  tendon-driven actuator has no entry for — the DoF standing for a tendon belongs to no
  connection, so the world deletes it as orphaned. Now measures the transmission: a
  tendon's length is the joints it wraps, each by its coefficient. Also removed a
  duplicated, shadowed `_end_build`.

## Outstanding

- `test_orm_generation.py::test_generation_needs_no_ros_message_package` — after the
  `json_msgs` deferral the generator reaches `GiskardWrapper._goal_result:
  JsonAction_Result | None`, a TYPE_CHECKING-only forward reference krrood's
  class-diagram builder cannot resolve.
- Then: merge #311 into #265, as the developer asked.
- Restacking onto `tracy_icra` once `tracy-demo-takes-the-integrated-branch` lands.

## For the developer to rule on

- **`TargetHoleMoved` moves the board, not one hole.** Departs from the mechanism the
  2026-09-09 roadmap entry settled, because holes and the board are on `FixedConnection`s
  and a hole is cut into the lid. Contract preserved; mechanism changed.
- **`PerceivedPoseOffset`'s person-instruction is my reading**, not stated anywhere.
- Tests were written after the implementation, not TDD. Recorded in roadmap.md.

## Environment (local only, nothing committed)

The real CI image runs here: `dockerd` is installed but not started; start it, pull
`ghcr.io/abdelrhmanbassiouny/cognitive_robot_abstract_machine:jazzy`, mount the checkout
at `/ws/cognitive_robot_abstract_machine`, `uv sync --extra dev --active` under
`/opt/ros/cram-env`, then run pytest from `/ws` exactly as `ci_reusable.yml` does. Far
more reliable than the ROS-stub scaffolding in `scratchpad/`.

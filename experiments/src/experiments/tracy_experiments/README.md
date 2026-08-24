# Tracy experiments

Tracy demos that drive the robot by commanding MuJoCo actuators directly rather than
through Giskard's live closed loop, because Giskard's own QP control loop reads
`world.state` as its belief of the robot's current position, and for a physically
simulated degree of freedom that same state is also written by Giskard's own prior
command -- so Giskard can be satisfied by its own prior write, not by the robot actually
having moved (see `equipment.py`'s own module docstring). Instead, every reach is planned
by Giskard against an isolated scratch copy of the world (`trajectory_planning.py`), and
the resulting trajectory is played back by commanding real MuJoCo actuators
(`real_time_simulation.py`).

## Layout

Shared infrastructure, used by both demos below, lives directly in this folder:

- `equipment.py` -- parse/mount Tracy, equip it with position-servo actuators, gravity
  compensation, self-collision exclusion; `add_cube`; `table_top_z`.
- `real_time_simulation.py` -- `RealTimeSimulation`, a wall-clock-paced MuJoCo mirror of
  a world, stepped from the calling thread (not MuJoCo's own background thread, whose
  reads would otherwise race a caller's own).
- `trajectory_planning.py` -- plan-then-execute primitives (`plan_cartesian_trajectory`,
  `plan_joint_trajectory`, `follow_joint_trajectory`, `park_arms`, `set_gripper`,
  `close_gripper_around`): Giskard plans kinematically against a scratch copy of the
  world, then the result is played back on the real, physically simulated one.
- `pick_and_place_action.py` -- `PickUpActionMujoco`/`PlaceActionMujoco`, matching the
  real `PickUpAction`/`PlaceAction`'s own field interface but driven by the primitives
  above instead of a Giskard motion mapping; generic over any body and arm, so both demos
  below build their action sequences from the same pair.
- `grasp_contact.py` -- MuJoCo contact-friction tuning (`GRASP_FRICTION`,
  `BOARD_FRICTION`, solver reference/impedance) for a grasped object and the surface it
  is released onto.
- `parkarms_demo.py` -- bare sanity check: mount Tracy on an empty floor and park both
  arms, no board/shapes/cubes at all.

Each task then has its own subfolder, both following the same `*_mujoco.py`/`*_real.py`
split -- `*_mujoco.py` has MuJoCo stand in as the real robot (as above); `*_real.py` has
the physical robot be the real robot, wired the way `coraplex_real_tracy/demo.py` wires
real hardware (`fetch_world_from_service` + `WorldSynchronizer` + the real
`PickUpAction`/`PlaceAction` + `ExecutionType.REAL`). The `*_real.py` files have not been
run against physical hardware.

- `montessori/` -- shape-sorting: pick up every loose Montessori shape that has a
  matching hole and place it above that hole (no fall-through check, no retry).
  - `world.py` -- `TracyMontessoriWorld`, the board and loose shapes built directly on
    Tracy's own built-in table.
  - `montessori_actions.py` -- `build_sorting_actions`, the shape/hole -> action-sequence
    builder shared by both entrypoints below (they differ only in which pick/place action
    class it's given).
  - `montessori_demo_mujoco.py` / `montessori_demo_real.py`.
- `stacking/` -- pick up a cube and place it on top of the growing tower, one pair of
  actions per cube, at a target pose precomputed from the start (not re-measured after
  each place).
  - `stacking_actions.py` -- `stack_target_pose`, the pure pose-precomputation function.
  - `stacking_demo_mujoco.py` / `stacking_demo_real.py`.

## What's working

Tracy runs the Montessori sorting task end-to-end without crashing; a full 5-shape run
completes cleanly every time. Both demos build one `PickUpActionMujoco`/
`PlaceActionMujoco` (or, on the `*_real.py` side, real `PickUpAction`/`PlaceAction`) pair
per object, composed via `coraplex.plans.factories.sequential` and run with
`plan.perform()` -- an ordinary coraplex plan, just with a `code()`-wrapped leaf instead
of a Giskard motion mapping.

Left arm is used throughout. Gripper closes about 25x faster than the URDF's own
declared limit (`equipment.GRIPPER_JOINT_VELOCITY_LIMIT`, raised from 0.032 to 1.0 rad/s
-- empirically tested: 2.0 breaks QP convergence and leaves the joint permanently
~0.016 rad short of target with `is_end_motion` never triggering; 1.0 converges cleanly).

## Real bugs found and fixed along the way

1. **Table-top height** -- `equipment.tracy_table_mount_position`/`table_top_z` use the
   table's own largest-area collision shape's top face, not the whole table body's
   bounding box: the latter also includes a taller fixed camera-pole structure riding on
   the same body, which put shapes spawned at that height ~0.25m above the real surface.
2. **Missing grasp contact tuning** -- without `grasp_contact.py`'s
   `apply_montessori_grasp_contact_parameters`/`apply_contact_friction`, loose shapes
   kept MuJoCo's soft contact defaults, which let a shape pinched between the fingers
   sink in and slip back out as the arm lifts.
3. **Park swept live through the board** -- parking via a driven trajectory (Giskard
   live or offline-planned-then-executed) always passed near the board on the way from
   Tracy's raw parsed pose, either raising `CollisionViolatedError` or physically
   knocking shapes around. Fixed: both arms start already parked, baked directly into
   the initial world state, so the simulation never sweeps through park at all.
4. **Drawer handles/board had no clearance** -- fixed via
   `montessori_demo_mujoco._strip_drawer_collision` (the drawers are unused by this demo
   anyway) and by moving the board out to clear both arms' own measured parked
   footprints.
5. **The "square"/cube shape wasn't actually a cube** -- `experiments.montessori.world`'s
   `_shape_body` gave every footprint-derived loose shape (cube, cylinder, rectangular
   prism) the same fixed 0.03m extrusion thickness regardless of its own footprint size,
   so the cube category came out ~22mm x 22mm x 30mm, not equal-sided. Fixed to derive
   the cube's thickness from its own clearance-scaled footprint edge instead, since it's
   the one category whose hole is actually square.

## Still open

- **Grasp reliability is marginal and unresolved.** Typically 1-2 of 5 shapes fully
  reach the board in a sorting run; the rest get nudged a few centimetres and don't get
  carried. Confirmed this is *not* a shape-orientation problem: two geometrically
  identical shapes (`circular_hole_1_shape`/`circular_hole_2_shape`) succeed/fail
  differently across runs, so a per-shape grasp-alignment fix would not address it --
  looks like a precision/timing-margin issue instead, not root-caused. This applies
  equally to the stacking demo and to both `*_real.py` files.
- `PickUpActionMujoco`/`PlaceActionMujoco`'s `grasp_description` field is accepted for
  interface parity with `PickUpAction` but not yet read -- every grasp is currently a
  fixed top-down approach regardless of what it's given.
- The `*_real.py` files are structurally wired the same way `coraplex_real_tracy/demo.py`
  wires real hardware, but have never been run against the physical robot.
- `grasp_contact.py`'s friction/solver values are not measured or validated against real
  hardware: the sliding-friction magnitude is a rough literature estimate for
  painted/finished wood (~0.25-0.4), and the solver reference/impedance values are
  MuJoCo-specific numerical contact-solver tuning with no real-world counterpart at all
  -- they were picked to stop simulation artifacts (finger penetration, an object
  slipping out mid-lift), not to model anything physical.
- `PickUpActionMujoco`/`PlaceActionMujoco` carry a `sim: RealTimeSimulation` and
  `actuators: Dict[str, Actuator]` field each, unlike the real `PickUpAction`/
  `PlaceAction`'s clean, ORM-mappable fields -- `experiments/scripts/generate_orm.py`
  sweeps the whole `experiments` package for dataclasses to map, so these two currently
  get swept up along with `RealTimeSimulation` itself, neither of which makes sense to
  persist to a database.

## How to run

```bash
# Montessori sorting
python -m experiments.tracy_experiments.montessori.montessori_demo_mujoco          # MuJoCo viewer
python3 -c "import experiments.tracy_experiments.montessori.montessori_demo_mujoco as demo; demo.main(headless=True)"
python -m experiments.tracy_experiments.montessori.montessori_demo_real            # physical robot

# Cube stacking
python -m experiments.tracy_experiments.stacking.stacking_demo_mujoco
python -m experiments.tracy_experiments.stacking.stacking_demo_real

# Bare park sanity check, no board/shapes/cubes
python -m experiments.tracy_experiments.parkarms_demo --viewer
```

The `*_mujoco.py`/`parkarms_demo.py` entrypoints need the `iai_tracy_description` ROS
package built and sourced, and the `experiments` package importable. The `*_real.py`
entrypoints additionally need a running Giskard/world-fetcher ROS stack for the physical
robot.

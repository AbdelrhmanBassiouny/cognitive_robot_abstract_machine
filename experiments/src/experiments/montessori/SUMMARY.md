# Franka Panda Montessori demo — handover

Status as of 2026-08-03. Branch: `mujoco_fixes_wip`. **Nothing is committed yet** — all
changes below are uncommitted working-tree edits.

## Goal

A second version of the Montessori shape-sorting demo (which on `tom/main` is driven by a
mobile HSR) driven instead by a table-mounted **Franka Emika Panda**, using this repo's
own friction-based physical grasping (as in `coraplex/demos/coraplex_panda_demo`) rather
than the HSR path's kinematic teleport-then-settle. Same scene, same shapes, same
narrative.

## Current state — what works

- **The Panda picks up a shape off the table, carries it across to its matching hole on
  the board, and places it there with ~5.5 mm horizontal accuracy.** The full
  pick-and-place executes end-to-end through `InsertMontessoriShapeAction`, no crashes.
- Both smoke tests reliably pick and move shapes (verified 4/4 runs incl. cube +
  triangular prism).
- All montessori + franka unit tests green: **63 passed, 8 skipped** (the 8 skip only
  because no `hsr_description`/`iai_pr2_description` is installed — expected).

## Current state — what does NOT work yet

- **Shapes do not fall *through* the holes.** They are placed precisely *over* the hole
  but rest on the board surface (e.g. cube ends at z≈0.608, board top ≈0.593). This is
  the documented board-clearance limitation, independent of the robot: the cube is
  0.03 m against a ~0.032 m hole (≈1 mm clearance/side; its diagonal exceeds the hole, so
  any rotation catches on the lip). **Tom's own later WIP fixed exactly this by shrinking
  the cube to 0.026 m** (constant `CUBE_EDGE_LENGTH`) and sizing the other shapes with
  clearance. See "Pending decisions".

## How to run

```
# The Panda demo (this work). Needs NO ROS robot package — reads the Panda straight out
# of coraplex_panda_demo/stacking_scene.xml. Downloads Panda meshes on first run.
python -m experiments.montessori.franka_montessori_demo --viewer     # real-time, watchable
python -m experiments.montessori.franka_montessori_demo              # headless

# Smoke tests (simpler: plain PickUp+Place, no hole insertion):
python -m experiments.montessori.franka_bare_pickup_smoke_test --viewer   # floor+table+arm+1 cube
python -m experiments.montessori.franka_pickup_smoke_test --viewer        # real board scene, --shape <category>
```

`python -m experiments.montessori.montessori_demo` is the **HSR** demo (needs
`hsr_description`; without it, it spawns the scene and does nothing — that is expected,
it is not the Panda demo).

## Files

New:
- `franka_panda_equipment.py` — `parse_panda()` (reads Panda from `stacking_scene.xml`,
  prunes the stacking cubes + actuators), `equip_panda_for_physical_simulation()`
  (per-joint position-servo actuators + gravity compensation + armature),
  `apply_grasp_contact_parameters()` (grasp friction/solref/solimp on loose shapes),
  `JointServoTuning` dataclass and the tuning/contact constants.
- `franka_montessori_demo.py` — the real demo: sorts every insertable shape into its hole
  via `InsertMontessoriShapeAction`, retry-with-jitter loop, RViz + live MuJoCo.
- `franka_pickup_smoke_test.py` — full-board-scene smoke test (one shape, PickUp+Place).
- `franka_bare_pickup_smoke_test.py` — minimal isolate-the-grasp scene (no board/other
  shapes), the vehicle used to debug the grasp.
- `test/experiments_test/test_franka_panda_equipment.py`,
  `test/experiments_test/test_montessori_fixed_base_robot_abstraction.py`,
  `test/experiments_test/dataset/synthetic_fixed_arm_robot.{py,urdf}` (a `HasOneArm`,
  *not* `HasMobileBase`, network-free mimic).

Modified:
- `world.py` — module-level `mount_stationary_robot()` (+ thin method wrapper),
  `add_robot_stand()`, `_spawn_free_body()`, the **`shapes_are_movable`** flag
  (default `False`, HSR untouched), `ROBOT_STAND_SCALE`.
- `insert_shape_action.py` — for a fixed-base robot (`not isinstance(robot,
  HasMobileBase)`): skips all navigation, and builds **concrete** `PickUpAction`/
  `PlaceAction` instead of the query-DSL (`a(...)`) form (see fix #8 below). Table lookup
  moved inside the mobile-base branch (fix #7).
- `test/experiments_test/test_montessori_world.py` — tests for mount/stand/movable shapes.

The whole `experiments/montessori/` package + `test/experiments_test/test_montessori_*`
were first ported verbatim from `tom/main`.

## The nine fixes that got the grasp working (debugging journey, for context)

1. **`shapes_are_movable`** — the ported shapes were `FixedConnection`-welded to the
   world, so MuJoCo treated them as immovable: the gripper could close on a shape but
   never lift it. This was the root cause of "closed fully but the cube didn't move".
   Opt-in flag added; the Franka path turns it on.
2. **`rotate_gripper=True`** — without it the Panda's wrist resolves the top-down grasp to
   a 45° orientation whose Cartesian descent never converges. (HSR doesn't need this.)
3. **Gripper stiffness 100 → 1000 N/m** (`/finger_joint1` tuning) — 100 N/m was
   "unrealistically soft" per `stacking_scene.xml`'s own comment; too weak to hold a shape.
4. **Contact params match the proven `coraplex_panda_demo` cube** — friction
   `[1, 0.05, 0.001]`, solref `0.008`, solimp `0.96 0.99`. The montessori shapes had
   MuJoCo's soft defaults (solref 0.02), which let a grasped shape slip out on lift.
5. **`apply_grasp_*` bug** — it *appended* a second `MujocoGeom`, but `MujocoBuilder`
   reads only the *first* one on a shape, so the override was silently ignored on the
   Panda fingers. Now modifies the existing `MujocoGeom` in place.
6. **`step_size` 5e-4 → 1e-4** — matches `coraplex_panda_demo` exactly; the coarser step
   under the same gains made the arm shake.
7. **Two-`Table` crash** — `add_robot_stand()` spawns a `Table`, so `[table] = ...get_
   semantic_annotations_by_type(Table)` unpacked two. Moved into the mobile-base branch.
8. **`EmptyUnderspecified`** — the action wrapped pick/place in the query DSL `a(...)`,
   which only resolves for the `ProbabilisticBackend`'s underspecified standing offset;
   a fixed-base robot has nothing underspecified, so it failed. Fixed-base branch now
   calls `PickUpAction`/`PlaceAction` concretely.
9. **Synthetic gripper joint states** — the concrete `PickUpAction` needs the gripper's
   `GripperState.OPEN`/`CLOSE` states; added to the `SyntheticFixedArmRobot` mimic.

## Pending decisions / next steps

1. **Fall-through** (biggest open item). Options discussed, not yet chosen:
   - *Shrink shapes* (recommended) — adopt Tom's WIP fix: cube ≈0.026 m + clearance on the
     footprint-derived shapes, so they drop through. Changes shared shape sizes in
     `world.py` (helps the HSR too, same direction Tom went).
   - *Leave as-is* — narrative becomes "places each shape onto its matching hole".
   - *Investigate board collision first* — check whether the box-grid collision leaves the
     openings truly clear at the current size, in case the lip is a decomposition
     artifact.
2. **Headless speedup (one-liner, not applied)** — the demo always runs `real_time_factor=
   1.0` (throttled to wall clock), even headless; the smoke tests use
   `real_time_factor=None if not --viewer else 1.0` to run as-fast-as-CPU headless. Apply
   the same to `franka_montessori_demo`'s `MujocoSim(...)` to make headless runs much
   faster; `--viewer` stays real-time on purpose. (The demo is also inherently slow: 6
   shapes × up to 3 attempts × a ~10-motion pick-place + 2 s settle, real-time-paced.)
3. **HSR `montessori_demo`** — only runs with `hsr_description` built/sourced. Not needed
   for the Panda work; decide separately if you want it.
4. **Add a skip-guarded live-Panda integration test** (task #7) mirroring
   `test_montessori_pr2_robot_abstraction.py`, skipped when `stacking_scene.xml`'s meshes
   aren't downloaded — pairs with the network-free synthetic-robot unit tests.

## Testing notes

```
python -m pytest test/experiments_test/test_montessori_world.py \
  test/experiments_test/test_montessori_semantics.py \
  test/experiments_test/test_montessori_hole_geometry.py \
  test/experiments_test/test_montessori_robot_abstraction.py \
  test/experiments_test/test_montessori_insertion_experience.py \
  test/experiments_test/test_montessori_demo.py \
  test/experiments_test/test_franka_panda_equipment.py \
  test/experiments_test/test_montessori_fixed_base_robot_abstraction.py
```

- `test_montessori_insert_shape_action.py`, `test_montessori_pr2_robot_abstraction.py`, and
  `test_montessori_mujoco.py` can't be *collected* in this environment: they import
  `experiments.orm.ormatic_interface`, which fails on `NavigateToPose.Goal`
  (`'NoneType' object has no attribute 'Goal'`). This is a **pre-existing** environment
  gap — it also breaks the untouched `test_sage10k.py` — unrelated to this work.
- Run `scripts/format_docstrings.py` on modified `.py` files before committing (needs
  `docformatter`, which is currently missing from `cram-env` — `black` alone was used so
  far).

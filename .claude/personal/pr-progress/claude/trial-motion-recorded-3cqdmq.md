# claude/trial-motion-recorded-3cqdmq - PR #319 (draft)

Base: `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265).
Session: https://claude.ai/code/session_013HepqhoucZF2H2cCjSizFP

## Done (original task)

1. giskardpy: `MotionStatechart.to_json`/`_from_json` carry `StateHistory`.
2. experiments: `RecordedTrial.motions: List[RecordedMotion]`; observer `ran_the_motion` +
   `ObserverMotionListener`; coraplex `GiskardExecutable.execute` tells
   `Context.motion_listener` (`ReceivesExecutedMotions`).
3. record_episode: `PerturbationChoice.LIGHTING_CHANGED` dropped.

## Done (CI round, 2026-09-12)

Both red jobs on #319 were red on the base branch too, byte-identical, and came from base
commits after the merge base. Fixed both here anyway:

4. `test_each_lib (version)`: `experiments` imports `physics_simulators` (base's
   `simulated_camera.py`) without declaring it. Declared it in `[project] dependencies`
   and the workspace group. Green in CI.
5. `test_each_lib (experiments)`: 4 failures in base's new `test_tracy_pickup_demo_mujoco.py`,
   all one root cause. `CAMERA_LINK_T_OPTICAL` assumed the plain link->optical quarter
   turns; against the `camera_link` `iai_tracy_description` states, all 8 shipped captures
   agree the real camera looked ~12 deg flatter and ~40 mm further along it. The simulated
   camera therefore looked too steeply, the board fell to the edge of the picture, and the
   look found 2 pieces instead of 4. Re-derived the constant from the captures against the
   frame the camera reports in (`tracy_mount`). File now 6 passed, 1 xfailed locally.
   Only `camera_on_tracy` reads the constant, so the real-robot demo is untouched.
   Open question for the author: why the real camera sits 12 deg off `camera_link`.

## Environment breakthrough (this container)

`iai_tracy_description` IS obtainable here after all: clone `code-iai/iai_tracy` (branch
`ros2-jazzy`), `UniversalRobots/Universal_Robots_ROS2_Description` (`jazzy`) and
`code-iai/ros2_robotiq_gripper` (`iai_dualarm`), then build a fake ament prefix with
`share/<pkg>` symlinks plus `share/ament_index/resource_index/packages/<pkg>` markers and
prepend it to `AMENT_PREFIX_PATH`. Tracy then parses and the Tracy tests run.
Scratchpad: `.../scratchpad/fake_prefix`.

Also: `psycopg2-binary` needed in `.venv` for the postgres URI; `service postgresql start`
then provision with `semantic_digital_twin/scripts/create_postgres_database_and_user_if_not_exists.sql`
(db `montessori_sorting`, user/password `montessori`).

## Still open

A trial's chart does not survive the database (`MotionStatechartDAO` has no columns;
`from_json` needs a world the engine's JSON deserializer cannot pass; nothing fills
`Episode.world`). Reported on the PR; separate change.


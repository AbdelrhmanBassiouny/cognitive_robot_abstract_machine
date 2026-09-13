## PR #351 - worlds are let go of once the scene built on them is dropped

Branch `claude/sdt-world-leak-37pd2z`, cut off
`claude/icra-experiments-simulation-pipeline-w4ep7n` (#265), draft PR #351 targeting it.

### Root cause (established, reproduced outside pytest)

`BaseSimulator.__post_init__` did `atexit.register(self.stop)` (and
`SimulatorRenderer.__init__` `atexit.register(self.close)`). atexit holds what it is
handed for the life of the process, in a C-level table `gc.get_referrers` cannot see -
which is why a referrer walk from a surviving World finds no root. Chain:
atexit -> `BaseSimulator.stop` bound to the MujocoSimulator ->
`read_data_from_simulator`/`write_data_to_simulator` (bound methods of the synchronizer)
-> `MujocoSynchronizer._world` -> `World`. Every MultiSim built and never stopped pins
its world. +11 worlds across `test_adapters/test_region_appearance.py` alone, on top of
the ~20 the session fixtures hold on purpose.

### Done

- Failing tests first: `test_a_simulator_that_was_never_stopped_is_collected`,
  `test_a_dropped_scene_lets_go_of_the_world_it_was_built_for` (commit 85cffe19b).
- Fix: `physics_simulators/shutdown_at_exit.py` -> `ShutdownAtExit` holds the method as a
  `weakref.WeakMethod`; simulator and renderer register/cancel through it
  (commit 3ac2a6338). Plus `test_shutdown_at_exit.py`, whose exit cases run a script in
  an interpreter of its own.
- Pushed, draft PR #351 opened with the `bug` label.

### Next

- Compare the live-world plateau over the full sdt suite before/after the fix locally
  (before: ratchets to 15-16 with 11 from the mujoco scene modules).
- Watch this branch's CI for `test_each_lib (semantic_digital_twin)`.
- Optional, offered by the user: merge #350 (coraplex CI hang fix) into this branch.

### Not done / out of scope

- The guard's limit, `count_worlds`, and the conftest fixtures are untouched by design.

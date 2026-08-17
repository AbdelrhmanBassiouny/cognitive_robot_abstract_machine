## Making the inline-ticking monitor cheap enough not to stutter

Fourth branch of this line of work. `montessori_merge_db_creation.md` records rounds
1-8, `stutter_montessori.md` round 9, `montessori_thread_safe_reads.md` rounds 10-12.
This branch is based on `stutter_montessori` -- the configuration that ticks the monitor
inline on the planning thread and so never had the segfault, only the stutter.

The bet: `montessori_thread_safe_reads` made a tick cheap in order to make it safe off
the planning thread. The same work makes the stutter go away when the tick stays *on*
that thread, and keeps the configuration that has never crashed.

### Round 13 -- the port

68. Cherry-picked all five of `montessori_thread_safe_reads`'s commits onto
    `stutter_montessori`. One conflict, in `event_monitoring.py`: `start()` spawns no
    thread here, so `_read_geometry_out` stays but as a warm-up (it keeps the one-time
    origin reads out of the first tick, which would otherwise stall a motion) rather
    than as a thread-safety measure. Dropped the `MUJOCO_LOG.TXT` that had been
    committed by accident.
69. Measured the same harness (`scratchpad/segmind_tick_timing.py`, 20 ticks) on both
    branches: **486.5 ms median on `stutter_montessori`, 73.1 ms after the port.** Note
    the branch's own docstrings claimed 99 ms; that number does not reproduce and was
    measured some other way. Worth telling the developer.

### Round 14 -- three more speedups

70. **`Bounds` answers for itself** (`geometry.py`): `from_points`, `empty`, `overlaps`,
    `contains`. Plus `NumericTransform.transform_points`,
    `KinematicStructureEntity.numeric_global_bounds` and
    `BoundingBoxCollection.enclosing_bounds`. `Bounds.empty` is what absent geometry
    reads back as, so no call site needs a special case.
71. **`InsideOf.compute_containment_ratio`** copied both meshes, transformed them, built
    a trimesh box around one and checked it was watertight -- to count vertices against
    six numbers. Now numpy. 73.1 -> 39.7 ms.
72. **`Shape.surface_area`** stated analytically instead of `shape.mesh.area`.
    `has_collision` was meshing every primitive in the world six times a tick; a
    cylinder's area is now 2*pi*r*(r+h) rather than its 16-gon's, ~3% larger.
    39.7 -> 25.6 ms.
73. **Bounds rejection before the exact relation** in `is_supported_by` (product-algebra
    intersection) and `is_body_in_region` (exact trimesh boolean). A rejected pair
    scored False/0.0 before too. 25.6 -> **12.5 ms**.
74. Total: **486.5 -> 12.5 ms, 39x.** A tick was 24 control periods at 50 Hz; it is now
    under one.
75. Raised `DEFAULT_TICK_RATE_HZ` from 2.0 back to 5.0 -- the value it had before the
    tick's cost forced it down. At 5 Hz the monitor takes a twentieth of the planning
    thread rather than half of it. Updated the docstrings and `--no-event-monitor` help
    that quoted 99 ms and said the switch was what made a watched run move smoothly.

### What is verified

- `scratchpad/segmind_monitor_casadi_trace.py`: still zero symbolic constructions off
  the main thread.
- sdt geometry/spatial-types/worlds suites: 386 passed, no new failures.
- Montessori monitoring/demo/script tests: 43 passed, 1 pre-existing failure
  (`test_shape_falling_through_its_hole_is_detected_as_pick_up_and_insertion`, confirmed
  failing on `stutter_montessori` too).
- segmind: the same 12 pre-existing `test_detectors` failures, no new ones.

### Known-unrelated failures in this environment

- `generate_orm.py` fails standalone with `Table '_MockedConvexSetDAO' is already
  defined`, which breaks collection of `test_world.py` and `test_gcs_polygons.py`.
  Worked around with `PYTEST_XDIST_WORKER=gw0`. **Worth the developer's attention.**
- The demo run the developer pasted died of `psycopg.errors.InsufficientPrivilege:
  permission denied for table ColorDAO` -- a database provisioning problem, not a code
  one -- and then segfaulted while unwinding from it. Not yet investigated.

### Round 15 -- recording is optional now

76. The developer's runs were dying at `results_session.commit()` with
    `psycopg.errors.InsufficientPrivilege: permission denied for table ColorDAO`. Root
    cause was **not** in the repository: `~/.bashrc` line 139 exports
    `FRANKA_MONTESSORI_SORTING_DATABASE_URI` pointing at
    `semantic_digital_twin_readonly` on port **5433**. The real database
    (`semantic_digital_twin` on 5432) is healthy -- 1635 tables, all owned by that
    role, insert allowed on every one. Told them; did not touch their `.bashrc`.
77. The pre-flight (`results_database.main`, run by `run_montessori_demo.sh` before
    anything else) only opened a connection, which a read-only role passes: the schema
    is already there, so `create_all` issues nothing and the first insert is what fails,
    a world build later. `verify_writable` now writes a table of its own and drops it.
    Dropped rather than rolled back -- SQLite's driver commits a `CREATE TABLE` whatever
    transaction it was issued in.
78. `ConfiguredDatabase` carries the URI together with `DatabaseUriOrigin`, so output can
    name the environment variable. A URI set in a shell profile appears nowhere in the
    command that was run, which is why this was invisible.
79. On the developer's instruction ("I do not want to record anyway so skip that part"),
    recording became best effort: `--no-record` asks for no database at all, and a run
    whose database refuses a write warns and sorts. `RecordsIterationsToADatabase` /
    `RecordsNothing` mirror `WatchesForEvents` / `WatchesNothing`.
80. First attempt gated this on origin -- exit 1 when the database was named with
    `--database-uri`, exit 0 when inherited. **Wrong, and the developer hit it
    immediately**: naming a database is not demanding to write to it. The live query
    panel reads recorded runs from the same place, and a read-only role serves that
    perfectly well, which is the whole reason to point a run at one. Only an
    *unreachable* database stops a run now (nothing can be read from it either);
    read-only always warns and carries on. `was_asked_for` is gone.
81. The demo also logged the URI *with its password in it*; it logs the masked label now.
82. **Verified against the real environment**: the pre-flight reports the read-only role
    in under a second and exits 0, and `--no-record` skips the check entirely.

### Round 14b -- soak

83. 900 s soak on this branch passed (6 passed, no signal). The developer separately ran
    the demo in a loop and reports **no stuttering**.

### Round 16 -- a missing database no longer stops a run

84. The developer asked why `FRANKA_MONTESSORI_SORTING_DATABASE_URI` "is not used
    automatically". It always was -- `ConfiguredDatabase.resolve` reads it. What they
    were seeing was the pre-flight *exiting 1* on it: `~/.bashrc:139` points the
    variable at port **5433**, whose cluster (`pg 17 main`) is down; only `pg 18 main`
    on 5432 is online. Round 15 made a read-only database survivable but left an
    unreachable one fatal.
85. `ConfiguredDatabase.resolve_reachable` now stands `IN_MEMORY_DATABASE_URI`
    (`sqlite://`) in for a configured database that cannot be reached, carrying the
    `UnreachableResultsDatabase` it replaced in `fell_back_from` so both the pre-flight
    (stderr) and the demo (log) can say why in their own channel. `main` never returns
    1 for a database reason now; the launcher's usage text and README said the demo
    "will not start without it" and no longer do.
86. **An in-memory database is per-connection**, so two things had to change or the
    fallback would have silently recorded into a database nobody could read:
    `create_results_engine` gives it `StaticPool` + `check_same_thread=False`, and the
    demo resolves *one* `ResultsDatabase` and hands the same object to both
    `_open_recording` and `_attach_cramera`. `open_recording` takes a `ResultsDatabase`
    rather than a URI for that reason.
87. `--database-uri` defaults to `None` instead of `configured_database_uri()`, so the
    run resolves its own and can name the origin.
88. 79 passed across the four affected suites. Two `caplog`-based recording tests fail,
    **confirmed failing on the unmodified code too** (caplog captures nothing in this
    environment); the `presets.json` failures in the live-query/episodic-memory suites
    are a missing `cramera/scenes/Franka_Montessori/` in this checkout.

### Round 17 -- the cramera/scenes submodule

89. The dead pin was **two** problems, not one. `2438a52` is unreachable because
    `cram2/cram-scenes` rewrote its history (old `014c879 garmi` -> new
    `2230683 garmi` + two more), so `submodule update --init` fails "not our ref".
    And `2438a52` was only a **5-line `index.json` insertion** -- the 34 MB
    `Franka_Montessori/` bundle it names was never committed anywhere, surviving only
    as *untracked files* in `~/Projects/copied/cognitive_robot_abstract_machine`.
    So re-pinning to latest could never have restored the scene.
90. `ef46d536b5` on `montessori_event_replay` had already done the minimal re-pin
    (`2230683` + a `skipif`). `cram2/main` has no `cramera` at all, so nothing central
    was ever broken by this.
91. On the developer's instruction ("can we make it a new PR onto cram2/cram-scenes?"),
    the bundle is now published: branch `franka-montessori-scene` on
    `cram2/cram-scenes`, commit `64b98ed`, parented on `2230683`. 69 files, the
    `index.json` entry re-applied byte-identically to `2438a52`'s. Dropped
    `stacking_scene.urdf` -- a leftover from the panda_stacking scene, referenced by
    nothing. Checked before publishing: no absolute paths, no secrets, all 59 mesh
    references in `panda.urdf`/`environment.urdf` resolve, and the repo commits meshes
    directly (921 already, no LFS) so 34 MB is in keeping.
92. **The developer has push access to `cram2/cram-scenes`** (verified with a dry-run
    push). No `gh` CLI and no token in this environment, so the PR itself has to be
    opened by hand at
    `https://github.com/cram2/cram-scenes/pull/new/franka-montessori-scene`.
93. Superproject pinned to `64b98ed` in `3153fa6d1a`. Safe to pin a PR-branch commit
    here in a way `2438a52` was not: it is actually pushed, and GitHub keeps
    `refs/pull/*/head` -- verified by fetching the SHA into a throwaway clone.
    **Re-pin to `main` once the PR merges.** Note this will conflict trivially with
    `ef46d536b5` when the branches meet; ours is the one to keep.
94. `presets.json` is unique to this bundle -- no other scene declares one -- and is
    still in sync with `MONTESSORI_PRESETS` (20 presets, scopes match). Both
    `TestDeclaredBundlePresets` suites now pass: 23 passed across live-query and
    episodic-memory, where two were failing.

### Environment quirks found while doing this

- `cramera` is not installed in the `cram` virtualenv (this repo's), only in `cram2`,
  which points at a *different* checkout (`~/Projects/copied/...`). Every test touching
  `experiments.orm.ormatic_interface` needs
  `PYTHONPATH=cramera/src:$PYTHONPATH` to collect. **Worth the developer's attention.**
- `cramera/scenes/` was empty here; fixed in round 17.

### Still open

- The run segfaulted *during teardown* after the SQL error, with
  `GLFWError: The GLFW library is not initialized` immediately before it. A viewer
  shutdown crash on the exception path, not the CasADi race -- no second thread is
  reading the world at that point. Needs the viewer to reproduce, so not chased.

### Next

- Head-to-head soak against `stutter_montessori` at equal wall clock would put a number
  on the end-to-end gain; only this branch has been soaked so far.
- `RotationMatrix.rotational_error` reports some rotations the long way round; latent
  bug, ask the developer.
- Still untouched: `TFPublisher` evaluating compiled CasADi from the physics thread, and
  `MujocoSimulator.add_entity` swallowing a viewer Pause (mujoco_simulator.py:1731).
- `body.global_pose` remains unsafe off-thread; callers wanting numbers should use
  `numeric_global_pose` / `numeric_global_transform`.
- No PR opened yet.


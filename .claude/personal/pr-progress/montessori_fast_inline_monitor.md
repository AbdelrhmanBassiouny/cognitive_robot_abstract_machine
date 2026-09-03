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
88. Committed as `a5b24bb3d2` and pushed to `origin/montessori_fast_inline_monitor`,
    one commit over the round-17 pin. 79 passed across the four affected suites. Two
    `caplog`-based recording tests fail,
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
94. The developer opened the PR: **`cram2/cram-scenes#1`**, still open (`main` is
    `2230683`). The pin commit is `11311d09e2`, **pushed to
    `origin/montessori_fast_inline_monitor`**. Verified the way it will actually be
    used: a fresh `git clone --branch montessori_fast_inline_monitor` followed by
    `git submodule update --init cramera/scenes` checks out `64b98ed` and yields the
    34 MB bundle. The one outstanding step is re-pinning to `main` after #1 merges.
95. `presets.json` is unique to this bundle -- no other scene declares one -- and is
    still in sync with `MONTESSORI_PRESETS` (20 presets, scopes match). Both
    `TestDeclaredBundlePresets` suites now pass: 23 passed across live-query and
    episodic-memory, where two were failing.

### Round 18 -- a flaky mesh download no longer kills the run

96. The demo died at `PandaMeshAssets.download_if_missing` with `503 Server Error` for
    `link6_4.obj` from `raw.githubusercontent.com`, 52 of 67 meshes in. The same URL
    answered 200 a minute later, so it was a momentary GitHub failure, not a bad
    reference -- and `raise_for_status()` turned it straight into a traceback.
97. `TransientFailureRetries` (5 attempts, 1 s doubling) now repeats a request while the
    host answers 429/500/502/503/504; anything else (404) is not retried. The give-up
    path raises `MeshDownloadFailed` naming the URL and status, and points out that
    meshes fetched so far are kept, so a rerun only fetches the remainder.
98. No try/except: the retry reads `response.status_code` rather than letting
    `raise_for_status` throw, and closes a transient answer unread so the connection
    returns to the pool.
99. Five new tests in `test/semantic_digital_twin_test/test_robots/test_panda_assets.py`
    against a queued-status HTTP stand-in and a two-mesh MJCF in the new
    `test/semantic_digital_twin_test/dataset/`. Ran the real download afterwards: all 67
    meshes present, 34.3 MB, and `parse_panda()` builds its 14-body world.
100. **Found while testing, not mine**: `98ac709d4a` ("moved the panda xml", sorinar329)
    deleted `PANDA_SCENE_BODIES_TO_DISCARD` from `franka_panda_equipment.py` but left
    its orphaned docstring at lines 50-53, and
    `test/experiments_test/test_franka_panda_equipment.py:7` still imports it -- so the
    whole `experiments_test` package fails to collect. Also present on
    `montessori_event_replay`. **Worth the developer's attention.**

### Round 19 -- the viewer opened on a scene the bundle does not have

101. The developer reported "robot scene could not be loaded". Cause: `cramera/scenes`'
    `index.json` ships `"default": "pr2_kitchen"`, a scene the bundle no longer carries
    (it is not even in the index's own `scenes` array). The viewer fetched
    `scenes/pr2_kitchen/scene.json`, got a 404 and stopped at "Scene failed to load";
    `SceneBundle.active_name` resolved the same dead name server-side.
102. Fix: a declared default is honoured only when the index also declares that scene,
    else the first declared scene is opened -- `Franka_Montessori` for this bundle.
    `ScenePicker.defaultScene` for the viewer, `SceneBundle.default_of_index` for the
    knowledge base, one per side that has to resolve it; the server logs which default
    it could not use. Committed `30bd734f53`, pushed.
103. Verified in Chrome against a server from this checkout (port 8712, `?live=127.0.0.1:9`
    so it could not touch the developer's running demo): the Franka Montessori scene
    renders, `ScenePicker.defaultScene` answers `Franka_Montessori`, 431 -> 431 cramera
    tests still pass plus 9 new ones.
104. **Their running viewer is not from this checkout**: pid 29803 is
    `~/Projects/copied/cognitive_robot_abstract_machine/.venv/bin/python -m cramera.server`.
    That clone needs the same fix (or to run cramera from here) before the symptom goes
    away for them.
105. The `GET /core/replay.js 404` in their log comes from a cached `index.html` of
    `montessori_event_replay`; nothing on this branch references that file.

### Round 20 -- the demo could not import its own ORM schema

106. The developer's `run_montessori_demo` died at `_open_recording` importing
    `experiments.orm.ormatic_interface`, whose line 102 pulls in
    `giskardpy.middleware.ros2.behavior_tree_config` -> `py_trees_ros` -> `ros2topic`
    -> `argcomplete`. Two modules were missing, for different reasons:
    - `argcomplete`: the `cram2` venv is built without system site-packages, so the
      system copy in `/usr/lib/python3/dist-packages` (the one ROS Jazzy's
      `ros2topic` counts on) is invisible to it. Installed `argcomplete` 3.7.2 into
      the venv; that half is fixed.
    - `json_msgs` (the next import in the same giskardpy chain, via
      `publish_feedback.py`): built only in `~/ros2_ws` (`cram_ros2_packages`,
      alongside `giskardpy_ros`), and `~/.bashrc` sources `/opt/ros/jazzy` and
      `~/Projects/ros2_ws` but never `~/ros2_ws`. Not touched (round 76 precedent:
      their shell profile is theirs); the developer needs
      `source ~/ros2_ws/install/setup.bash` before running.
107. Verified: with that overlay on the path the full `ormatic_interface` import
    succeeds in `cram2` from this checkout.
108. Design smell worth raising: the ORM interface importing a ROS2 behavior-tree
    config means a `--no-rviz` demo cannot record results without a sourced ROS
    workspace. Per AGENTS.md that file is regenerated, so the fix would go through
    `scripts/regenerate_all_orm.py` / what feeds it, not the file.

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


### Round 21 -- the 2026-09-01 merge of main (`/plan-item-resolve`)

Thirteen days without a push while `main` reached `1227a68f`, 353 commits on. Nine
`stacked-pr-maintenance` passes had reported the conflict on #169 and skipped the branch.
Merged as `3e9f3847`; #169 went `dirty` -> `unstable`.

What the 25 conflicts actually were, and how they went:

- **The ORM interfaces**: `main` had ported the same `ijcai-tutorial` machinery and
  carried it much further (staleness detection, one interpreter for every generator, a
  progress bar, a pytest `--orm-build` option). Took `main`'s whole side, losing
  `ensure_generated`. Kept `scripts/ensure_orm_interfaces.py` as the demo's pre-flight,
  rewritten over `is_outdated` + `regenerate`, because a demo run is not a test run.
- **The bounding boxes**: `main` renamed `BoundingBox` -> `VolumetricBoundingBox`, added
  `PlanarBoundingBox`, and factored `AxisAlignedBox` out -- absorbing this branch's own
  `Bounds`/`to_array_bounds` generically. Carried the numeric origin onto that base
  rather than one subclass, replaced its symbolic `transform_to_origin` with the numeric
  one over a new abstract `axis_bounds`, and dropped `axis_intervals`/`origin_translation`
  as redundant once the origin holds numbers. Fixed both `__eq__`s, which compared
  origins with `np.allclose` (no array once the origin is a `NumericTransform`); two new
  tests on `PlanarBoundingBox` fail without the fix.
- **MuJoCo syncing**: `main`'s `JointBackedConnection` + model-lock structure taken, this
  branch's setpoint ramping kept on top, with `_measure_command_interval` before the push.
  Kept this branch's `_compute_keyframe_qpos` (walks the compiled model's joint order).
- Smaller: `PickUp`/`Placing` take `main`'s thresholds and still gate their attach/detach
  nodes; `forward_axis` is a `classproperty` now; krrood's tuple-collection fixes went to
  `main`'s wording (the branch's `COLUMN_VALUE_TYPES` ORMatic fix auto-merged and stays);
  experiments conftest took `main`'s `CEREAL_NAME`.

### Environment (this container)

Claude Code on the web, no CRAM workspace at all: Python 3.11 as `python3` (repo needs
3.12, which is installed as `python3.12`), no numpy, no sqlalchemy, no ROS. Nothing could
be run. The static battery that *is* available here and was used:
`python3.12 -m py_compile`, `pyflakes` in a hand-built 3.12 venv, `black`+`docformatter`
via `scripts/format_docstrings.py` (needs the venv's `bin` on `PATH`), and
`git merge-tree` against `main`.

The pyflakes differential needs both line numbers *and* "from line N" back-references
stripped, or the `Color` re-definitions in `geometry.py` show up as eight false
positives.

The `.claude/` tooling on this branch predates `plan_item_bootstrap.py update`, so the
manifest writes were run from a scratch worktree of a branch that has the current
tooling.

### Next

- CI on `3e9f3847` is the real check; nothing about the merge was verified dynamically.
- The five branches stacked above this one, plus #176, #177 and #178, are stale by this
  merge and need restacking.
- `cramera/requirements.txt` is now the last of its kind (`main` deleted fourteen and
  moved to inline `pyproject` dependencies). Left alone so as not to conflict with #168.
- Earlier "Next" items below still stand: the head-to-head soak, `rotational_error`,
  `TFPublisher`, `MujocoSimulator.add_entity`, `body.global_pose`.

### Round 22 -- what CI said, and the check that would have caught it

Six red jobs on `3e9f3847`, fixed in `82a2c0a8e`.

**Mine, three of them, all one shape** -- `main` moved something, the auto-merge kept
the branch's use of the old place, git said nothing:

- `insert_shape_action.py`: `translate_free_space_to_where_condition` ->
  `GraphOfBoundingBoxes.constrain_to_free_space`, `navigation_map_at_target` ->
  `PlanarGraphOfBoundingBoxes.navigation_map_at_target`, and the same stale 3D query
  point `main` fixed in `sage10k_actions.py` (`1a6d4206e` is the commit to read).
- `PickUpAction`: `grasped_object=self.object_designator` needed `.root`, like every
  other use in that method.
- `WORKSPACE_ORM_INTERFACES`: `experiments` declares `("coraplex", "segmind")`.

**Mine by omission**: `cramera/requirements.txt`. Round 21 left it "valid setuptools,
not worth conflicting with #168"; `main` tests the convention in
`test_dependency_declarations.py`. Now inline, file deleted, and `experiments` declares
`cramera` + `segmind`.

**The branch's own, red before the merge**: `apply_grasp_contact_parameters` friction
arity, `MontessoriLiveEventSource(clock=...)`, and the `parse_panda` mesh download race
(two xdist workers, one `.partial` name).

### The differential's second half

`pyflakes` is per-file: it cannot see that `from x import y` names something `x` does
not define. `$SCRATCH/check_imports.py` (kept in the round's scratchpad; worth
re-writing rather than hunting for) parses every such import, resolves the module to
its file, follows `import *` through `__init__.py`, and reports the misses. Merge vs
branch: identical, 41 either way, all long-standing noise (segmind SCRDR generated
models, ROS shims). Run it as a *difference*, like the pyflakes one.

### What runs in this container after all

More than round 21 assumed. With a hand-built 3.12 venv (`pytest`, `packaging`,
`requests`):

- `test/version_test/test_dependency_declarations.py --noconftest` runs outright: 22
  passed. Pure `tomllib` + `re`, no workspace.
- `panda_assets.py` can be loaded by path with `semantic_digital_twin.exceptions`
  stubbed, which is enough to drive `download()` and show a pin failing before the fix.
- The ORM declaration assertion is a dozen lines of `ast` over the generators.

Anything importing `semantic_digital_twin` proper still cannot: `rustworkx`, then
numpy, trimesh, casadi.

### The one that looked like it needed the workspace, and did not

`test_shape_falling_through_its_hole_is_detected_as_pick_up_and_insertion`, red since
before the merge base, was a single missing argument. `move_to` assigned a frameless
matrix to the shape's connection origin; that setter transforms into the parent frame
and so needs the frame stated, and it raised on the *first* move -- the test never
reached the movement it exists to check, nor its three assertions.

The frame is not a guess: the coordinates come from `global_transform`, so they are the
world root's, and `MontessoriWorld._spawn_free_body` joints a movable shape straight to
`world.root` and writes its own origin with exactly that frame. The transform is an
identity, which is what made it safe to push from here. `085f160f9`.

Open: whether the three assertions hold, now that they run at all. CI answers that.

Worth generalising: "needs the workspace to chase" was wrong here, and the tell was
that the traceback names the *test's own* line, not production code. A failure whose
cause is visible in the test source is worth reading before it is deferred.
### Round 23 -- the second CI round

109. **`PickUpAction` wants the annotation, not the body.** Eight `experiments` tests
    died on `'Body' object has no attribute 'root'`. `main` retyped
    `PickUpAction.object_designator` (and `ReachAction`'s) from `Body` to `HasRootBody`
    and takes `.root` at every use *inside* the action; the montessori callers were
    pre-applying `.root`. Fixed at both `insert_shape_action.py` sites (459, 481) --
    and note the two `PlaceAction` calls ten lines below each of them keep their
    `.root`, because `PlaceAction.object_designator` is still a `Body`.
110. **This is the reverse of round 22's `pick_up.py` fix, and both are right.** One
    type change produces errors in opposite directions on either side of the boundary:
    uses inside the action gained `.root`, callers lost it. Worth remembering before
    "fixing" one by analogy with the other.
111. Same call site in the two Franka pickup smoke scripts, neither of which CI runs.
    `franka_pickup_smoke_test.py` had a `MontessoriShape` in hand already. The bare one
    builds an unannotated cube on purpose -- but its docstring's "bare" is about the
    scene carrying no sorting board, not about semantics, and there is no way to name an
    unannotated body to `PickUpAction` any more, so it is annotated as `CubeShape`.

### The world budget

112. `semantic_digital_twin` tripped `count_worlds` (`test/conftest.py`), an autouse
    module-scoped guard failing once `objgraph.count("World") > 30` after a
    `gc.collect()`. Shared by the whole run, checked at every module boundary, under
    `-n auto` -- so which worker crosses it varies, which is why exactly one module
    reported it.
113. Found by elimination, not by guessing: of every fixture in `test/conftest.py`,
    `armar7_world_state_reset` is the only one any `test/semantic_digital_twin_test`
    file requests on this branch and none does on `main`; `_armar7_world_setup` behind
    it has **no user anywhere on `main`**. So main's sdt job never builds an Armar7
    world and this branch's builds one and holds it for the session. The one-liner that
    establishes this is worth keeping:
    `for n in $(fixture names); do compare grep -rl over HEAD vs git grep -l over origin/main; done`.
114. `test_world_armar7.py`'s second test mutates the drive origin, which is the only
    reason it wanted the deepcopy-and-restore wrapper. A per-test world serves it
    better; conftest gained a function-scoped `armar7_world` over the existing
    `world_with_urdf_factory`, and nothing the test asserts changed. Main's two fixtures
    are left exactly as they are -- unused, as they are on `main`.
115. **Why it took until now**: the sdt suite had *never run on this branch*. Every run
    back to `da2e062e3` failed at `Build ORM` and skipped `Run tests` outright; the main
    merge brought the machinery that lets the job reach pytest. Not a merge regression --
    a suite addition that had never been measured.
116. Limit worth stating: the world-budget fix is reasoned, not measured. The reasoning
    is exact about what the branch *adds* (one session-held world, and nothing else) and
    silent about how close main's own baseline sits to 30. `4150026be`; CI is the check.
117. `scripts/format_docstrings.py` reflowed two docstrings it had never been run over.
    Kept the `TABLE_TOP_SCALE` one (a proper summary/body split); reverted the other,
    which wrapped as `full hole-\ninsertion`.

### Round 24 -- the six-hour coraplex job

118. **Not slow, hung.** `test_each_lib (coraplex)` had been hitting GitHub's six-hour
    job limit on every push since the merge. The workflows declare no `concurrency`
    group, so every superseded run kept a runner for its whole six hours; six were
    cancelled by hand. Worth proposing a `concurrency` group to the developer.
119. The log pins it without ambiguity: `test_training_environments.py::test_move_to_reach`
    starts on `gw1` at 07:56:55 and never reports again, `gw0` drains its queue by
    07:57:15, and the session waits on `gw1` until cancellation. **Read an xdist log for
    a started-but-never-reported item**, not for the last line printed -- the last line
    was a passing test on the *other* worker and points nowhere.
120. That test is `main`'s and untouched here. It samples two random reach episodes and
    asserts only `success_rate >= 0.0`, because unreachable targets are expected: the
    tick budget is what makes one a failure instead of a hang.
121. **The regression**: `main` ticks `while counter < len(self.motion_mappings) * 2000`
    then raises `MotionDidNotFinish`. Making the budget configurable here defaulted it
    to `None` and read `None` as "tick until the motion ends" -- `while True` for every
    caller that does not ask, which is everything except the three montessori scripts.
122. Fixed in `d21071ca5`: `DEFAULT_MAX_TICKS_PER_MOTION_MAPPING = 2000`, the ClassVar
    is an `int`, the unbounded path is gone, and the bound is a `tick_limit` property.
    `ExecutionEnvironment.max_ticks_per_motion_mapping` stays `Optional` -- there
    `None` means "leave unchanged", a different thing.
123. **The test had to be on the bound, not the hang.** A test that sets a small budget
    passes against the broken code too, since only the *default* regressed; and the
    default is 4000 real QP ticks. So it asserts `tick_limit` is finite and equals
    `len(motion_mappings) * DEFAULT_MAX_TICKS_PER_MOTION_MAPPING` with no environment
    budget set.
124. Flagged, not fixed: `SimulationTimePacer.sleep()` spins on the simulation clock
    with no bound, so a stalled sim blocks a tick forever and the budget cannot help.
    Unreachable from tests (only the demo scripts set `context.simulation_clock`), but
    a real hang in the demo. The timeout policy is the developer's call.
125. `scripts/format_docstrings.py` split a `:py:attr:` target across a line
    (`...GiskardExecutable\n.max_ticks_per_motion_mapping`), which Sphinx cannot
    resolve; reverted that hunk. Second round running that it has damaged a docstring
    it had never been run over.

### Round 25 -- the gripper, and a test with no fix behind it

126. The bound worked: coraplex finished in **14:46**, 3 failed / 415 passed, and
    `test_move_to_reach` -- the test that had been hanging for six hours -- passed.
127. **Two failures and the Tracy demo hang were one bug.** `_goal_state` assigns the
    object's half-width *in meters* to every finger connection. That is what the
    Panda's model means (`type="slide" range="0 0.04"`, sliding along the axis the
    width is measured on). Nothing else here does:
    - Tracy (Robotiq 85): open `[0.0, 0.0]`, closed `[0.8, -0.8]` **radians**,
      antisymmetric. Both knuckles got the same small positive number -> wrong unit,
      wrong sign, never converges.
    - PR2: open `[0.548, 0.548]`, closed `[0.0, 0.0]` -- the Panda's *sign* convention
      in radians. Wrong the same way but silent: the number lands in range, so it
      converges to a meaningless angle.
128. Gated on `isinstance(connection, PrismaticConnection)` for every finger
    connection. **The joint type, not a guess from the numbers** -- a prismatic joint's
    position *is* a displacement in meters, which is the whole premise of the sizing.
129. One predicate now decides the goal *and* the tightened threshold. They were
    computed independently, so any fallback in one would have tightened the threshold
    against a goal that was never resized.
130. **Why the demo kept hanging after the tick bound**: it runs `ExecutionType.REAL`,
    and `_execute_real` is a single call into giskard that waits. The budget added for
    `_execute_simulation` does not reach it. Worth remembering before assuming a bound
    covers every execution path.
131. The PR2 test asserted the *threshold*, never the goal -- which is exactly why the
    units bug survived there. Retargeted to assert the new contract. Note the
    tight-threshold behaviour is now pinned only end-to-end by the montessori Panda
    suite; coraplex has no prismatic gripper to test against.
132. **The third failure was a TDD cycle nobody finished.**
    `test_spin_thread_ends_quietly_when_somebody_else_ends_the_context` came in with
    `08257863` and `git diff origin/main...HEAD -- coraplex/src/coraplex/demonstrations.py`
    is *empty* -- the test was written, the fix never was. It has never passed. An
    earlier note here called it pre-existing "on this branch and its parent alike",
    which was true and misleading: the parent is another branch of this same stack.
    **Check whether a "pre-existing" failure has a fix behind it at all.**
133. `executor.spin` ran as the thread target; rclpy raises `ExternalShutdownException`
    out of it when the context's owner ends it and, unlike the executor's own shutdown,
    does not swallow it. `_spin_until_the_context_ends` returns on it.

### Round 27 -- the base branch merged main again

134. #244 merged `main` a second time (`95f8483b`) after this branch last took it at
    `f38b9e87`, and the pull request went `dirty` while the manifest still said
    `blockers: []`. CI on the head `c8bf6f05` was **green in all 24 checks**, so the
    conflict was the whole of the blocker.
135. Five files, all the same shape as every round before: main moved something this
    branch's work sits on. `plans/executables.py`, `actions/core/pick_up.py`,
    `.../placing.py`, `ormatic_experiments/scalability.py`,
    `test_plan/test_executables.py`.
136. **`GiskardExecutable` was rewritten upstream.** The motion state chart is a field
    parsing fills in, terminated by a new `prepare_for_execution`; the pause/interrupt
    monitors and `is_paused` are gone, and `_add_condition_monitors` is kept but
    unused while main reworks it. Main's structure taken, this branch's `tick_limit`
    and pacer kept in the loop.
137. The loop's `if self.is_paused: continue` guard went with the monitors its comment
    names. Checked before dropping it: the only reader was the loop itself, and the
    demo pauses between plans through `wait_while_paused`, not through the executor.
    **Coraplex plan-level pause now reaches nothing** -- main's state, flagged in the
    pull request rather than half-revived here.
138. **The silent conflict, and the first that is not import-shaped.**
    `PlanNodeGroup.of_plan_node_kind` keys the attachment colour on the *strings*
    `"AttachNode"` and `"DetachNode"`; main replaced both with `ReAttachNode`, so every
    attachment step of a live plan fell to `OTHER` and lost its colour. Git touched
    neither line. Reproduced directly in this container
    (`of_plan_node_kind('ReAttachNode') -> other_plan_node`), then fixed.
139. Both existing tests spell a dead name out, which is why neither noticed -- the
    exact failure AGENTS.md describes. The new test reads the name off
    `ReAttachNode.__name__`. The old names stay mapped: a bundle recorded before the
    rename carries them, and that method reads recorded plans too.
140. **The check that found it, worth keeping**: after resolving, list every call site
    of whatever the incoming side renamed or centralised, *including the ones spelled
    as strings*. Neither pyflakes nor the import resolver can see a name in a dict key.
141. `semantic_digital_twin/adapters/multi_sim.py` still says AttachNode/DetachNode in
    four docstrings. That file is #244's now, so it was left alone rather than pulled
    back into this diff. **Worth mentioning to whoever holds #244.**

### What this container could and could not do

- No CRAM workspace: no numpy, no sqlalchemy, no ROS, python3.11 as `python3` (3.12 is
  installed). No suite ran.
- What did run: `python3.12 -m py_compile`, `scripts/format_docstrings.py` (needs a
  hand-built 3.12 venv with black, docformatter, tqdm), both halves of the
  undefined-name differential, and `cramera.knowledge.enums` imported by itself with
  only `typing_extensions` installed -- which is what made the attachment bug
  reproducible rather than merely argued.
- The import-resolver half is worth rewriting rather than hunting for; it is ~80 lines
  of `ast` over every `from <workspace module> import <name>`, following `import *`
  through `__init__.py`. Run it as a *difference* against both parents: 13 findings
  either way here, all long-standing.
- `format_docstrings.py` did not damage anything this round. Checked first that main's
  own copies of the five conflicted files are already black-clean, so it could only
  touch the resolutions.

### Round 28 -- the monitor half split out as #256

142. The developer asked whether everything `icra-experiments` needs from #169 could move
    into #244. It can, and it should not: #244 is already slated to split into three, and
    #169 is 164 cramera files out of 272. So a third pull request between them, **#256
    `montessori_monitor_and_recording`** -- 35 files, no `cramera` import anywhere.
143. **`tracy_icra` is what settled the cut.** The ICRA demo branch has no cramera and its
    own `montessori_demo.py`, so the demo entry point never had to cross. Worth the check
    before scoping a split: ask what the consumer actually runs, not what its notes name.
144. Three imports pointed the wrong way. `MethodPatch` -> `krrood.patterns.method_patch`;
    `sorting_progress` reads `NumericPose` from sdt, where it is defined, not from
    cramera's re-export; the one test driving a monitor into `MontessoriLiveEventSource`
    stayed with that adapter.
145. `SortingRunControl` **subclasses cramera's `LiveRunControl` ABC** and its clock is
    `cramera.live.run_clock.RunClock`. Only `title`/`state`/`apply` (~40 lines) speak
    cramera's vocabulary; the rest is demo state pointing the wrong way. Inverting it is
    the price of moving the demo entry point, and it was not paid.
146. Second native-stack dissolve on this plan. #247 recorded, unstacked, #169 retargeted,
    re-created as **#258**: `244, 256, 169, 170, 164, 165, 167, 168`. The
    `stacked-pr-maintenance` procedure worked verbatim; `GH_TOKEN` is set in this
    container, so the curl half is available here.
147. `format_docstrings.py` split the `:py:attr:` target
    `GiskardExecutable.max_ticks_per_motion_mapping` across a line again -- **third time on
    this line of work**. Reverted on #256 so the two branches stay identical.

### What runs in this container (updated)

- `test/version_test/test_dependency_declarations.py` runs with `--noconftest` in a
  hand-built 3.12 venv: 20 passed, and it is what pins the `segmind` declaration
  `experiments` needed once it imported segmind.
- `cramera.knowledge.enums` and `krrood.patterns.method_patch` import standalone with only
  `typing_extensions`, which is how the attachment-colour bug was reproduced rather than
  argued.
- The cross-module import resolver is the check that a *subset* dangles nothing. Run it
  against both parents and compare; 13 long-standing findings either way here.


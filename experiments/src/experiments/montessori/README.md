# Montessori shape-sorting demo

A table-mounted Franka Emika Panda (see `franka_montessori_demo.py`) sorts loose
Montessori shapes into a shape-sorting board's matching holes, in MuJoCo, with segmind
event detection running alongside the ground-truth geometry check. Every iteration's
per-shape result is persisted to a Postgres database via ORMatic (see
`sorting_results.py`).

## One-time setup: the results database

Only needed if you want the results kept past the run. No database problem stops a run:
one that will not take a write is sorted alongside and simply not recorded to, and one
that cannot be reached at all is replaced by a SQLite database inside the demo's own
process, which the viewer's episodic-memory questions are answered from until the run
exits. `--no-record` asks for no database at all.

Persistence needs a Postgres role and database to already exist. Provision them once,
as the `postgres` superuser, with the script `semantic_digital_twin` already ships for
this:

```
sudo -u postgres psql -f semantic_digital_twin/scripts/create_postgres_database_and_user_if_not_exists.sql \
  -v db_name="franka_montessori_sorting_results" \
  -v user_name="semantic_digital_twin" \
  -v user_password="montessori"
```

This matches `results_database.py`'s own `DEFAULT_DATABASE_URI`
(`postgresql+psycopg://semantic_digital_twin:montessori@localhost:5432/franka_montessori_sorting_results`);
override it per run with `--database-uri`, or for every run with the
`FRANKA_MONTESSORI_SORTING_DATABASE_URI` environment variable.

If the role already exists with a different password, either set it to the one above
or point the run somewhere else with `--database-uri`. `run_montessori_demo.sh` checks
this before it starts anything, so a mismatch is reported in a fraction of a second
rather than after a world has been built — and says which of the three settled on the
database, since a URI inherited from a shell profile appears nowhere in the command
that was run.

## Running a single iteration

```
python -m experiments.montessori.franka_montessori_demo --world2 --no-rviz
```

- `--world2` uses `world2.py`'s layout (board directly ahead of the robot, loose shapes
  on a separate stand to its side) instead of the default single-table layout.
- `--no-rviz` skips TF/marker publishing, since nothing is watching it outside of
  `--viewer`.
- Add `--viewer` to open a MuJoCo viewer window instead of running headless.

## Running multiple iterations, with a forced real-time factor

Headless runs default to `real_time_factor=None` (as fast as the CPU allows).
Real-time pacing was observed to change insertion outcomes for at least one shape
(`circular_hole_1`'s fell-through rate went from ~30-55% unpaced to 95% real-time paced
in a 20-iteration run -- see `circular_hole_1_tuning_log.md`), so a run meant to produce
comparable, trustworthy ground truth should force it via
`headless_realtime_pacing_runner.py`, which monkeypatches `MujocoSim` to
`real_time_factor=1.0` and then passes every argument straight through to
`franka_montessori_demo`:

```
python -m experiments.montessori.headless_realtime_pacing_runner \
  --world2 --no-rviz --iterations 5 --exit-after-sorting
```

`--exit-after-sorting` matters here: without it, a single-iteration run idles
afterwards for inspection; with `--iterations` greater than one it is implied anyway,
but pass it explicitly for a scripted run so nothing is left waiting on a `--viewer`
that was never opened.

### Preferred for anything more than a couple of iterations: `batch_runner.py`

Running many iterations in one long-lived process is not reliable (see **Known bugs**
below). `batch_runner.py` restarts `headless_realtime_pacing_runner` in a fresh
subprocess every `--batch-size` iterations instead, so a crash only loses the batch in
progress rather than every iteration run so far:

```
python -m experiments.montessori.batch_runner --world2 --no-rviz \
  --database-uri "postgresql+psycopg://semantic_digital_twin:montessori@localhost:5432/franka_montessori_sorting_results" \
  --total-iterations 20 --batch-size 5
```

`--database-uri` is required here (there is no default, unlike `franka_montessori_demo`
itself). Every batch's iterations are committed as they finish, regardless of which
subprocess ran them.

## Resuming after a crash or an interrupted run

Nothing needs to be redone: every iteration commits to the database as it finishes
(one `SortingIterationResult` per iteration), so a run that died partway through has
already kept everything up to that point. Continue from where it stopped with
`--start-iteration`, pointed at the same database:

```
python -m experiments.montessori.batch_runner --world2 --no-rviz \
  --database-uri "postgresql+psycopg://semantic_digital_twin:montessori@localhost:5432/franka_montessori_sorting_results" \
  --start-iteration 4 --total-iterations 2 --batch-size 1
```

`--start-iteration` only changes the recorded `iteration` number stamped on each new
`SortingIterationResult`; it does not read the database to figure out where a previous
run left off, so pick it yourself (e.g. `SELECT MAX(iteration) FROM
"SortingIterationResultDAO"` against the same database, plus one). `franka_montessori_demo`
itself takes the same `--start-iteration` flag for a single long-lived process.

## Reading the results back

See `segmind_event_query_examples.py` for a handful of worked example queries
(segmind detection accuracy against ground truth, per-shape results across every
iteration, pick-up-to-insertion timing, ...), and `segmind_event_query_report.py` to
run and print all of them against a real database without writing any code:

```
python -m experiments.montessori.segmind_event_query_report
python -m experiments.montessori.segmind_event_query_report --shape-key circular_hole_1
```

## Asking the running demo questions

`--cramera` serves the world and the running sort to the cramera viewer from inside the
demo process. `run_montessori_demo.sh` at the repository root starts both together and
takes any demo argument:

```
./run_montessori_demo.sh
./run_montessori_demo.sh --only-shape square_hole
```

It runs with `--world2 --viewer --no-rviz` unless you say otherwise, since it exists to
watch a run rather than to batch one; `--no-world2`, `--no-viewer` and `--rviz` take
those back. The demo module's own defaults are unchanged, so the headless batch runners
are unaffected.

RViz publishing is off by default here because you are watching through the viewer
instead, and because it is not safe to leave on for a long run: `TFPublisher` evaluates
a compiled CasADi expression from the physics thread every time the simulation syncs its
state back (100 Hz), while the plan thread builds CasADi expressions of its own. CasADi
releases the GIL and reference-counts its nodes without atomics, so the two corrupt each
other and the process eventually dies of a segmentation fault inside CasADi. Pass
`--rviz` if you need the markers and accept that risk.

Or run the two halves yourself:

```
python -m experiments.montessori.franka_montessori_demo --viewer --cramera
./run_cramera.sh    # then open http://localhost:8711/
```

Leave `?scene=` off the viewer URL: it only attaches to a running demo by itself when
the page names no recorded scene.

The viewer's *Live* button appears within a few seconds, and the EQL panel's buttons
become this demo's own questions, offered under two headings.

### Current State Queries

Answered from the sort as it runs rather than from the database once it finishes. They
cover three things:

- **Was this shape inserted?** `shape.is_inserted` is the same geometric ground truth
  `ShapeSortingBoard.has_fallen_through` gives, re-read after every attempt. A shape
  names itself by what it *is* (`cube`, `cylinder_1`) rather than by the hole it is
  aimed at; the world names every loose shape after its hole (`square_hole_shape`), so
  `shape.name` would otherwise read as though the piece were the hole. `shape.shape_key`
  keeps that pairing, and is the key results are recorded under.
- **Where was it being inserted?** `shape.target_hole` and `shape.target_pose` name the
  hole and the pose the attempt aims to release the shape at.
- **Why could it not be?** `attempt.failure_reason` prefers the plan's own failure when
  it names a cause, and otherwise reads the segmind events: never picked up, dropped out
  of the gripper before the insertion phase, released off target, or wedged in the hole.
  See `insertion_diagnosis.py` for the ranking.

Four variables are in scope: `shape`, `attempt`, `plan_step` and `event`.

Nothing is persisted by this path — it reads the in-memory record in
`sorting_progress.py`, which is why answers are available mid-run while the database
only sees a completed iteration.

### Episodic Memory Queries

Answered from `--database-uri`, so they describe every run already recorded there rather
than the one on screen: how often each shape was sorted, how its attempts ended, and
every recorded run. One variable is in scope, `shape_result`
(`sorting_results.ShapeInsertionResult`), together with `InsertionOutcome` to compare
against and `sum` (left out of EQL's own namespace, since it shadows the builtin).

The query is translated to SQL by `krrood.ormatic.eql_interface.eql_to_sql` and run where
the results live, so a database with thousands of iterations is grouped by the server
rather than loaded into the demo process.

> There is deliberately no "most likely failure" column. Expressing it needs `mode`,
> which the EQL-to-SQL translation does not cover and which has no portable SQL aggregate
> behind it. *how did each shape's runs end?* answers the same question by giving the
> per-outcome counts to read off instead.

### Both

The question set lives in `live_query_source.py` and is mirrored into the recorded
`Franka_Montessori` bundle's `presets.json`, which a test keeps in step.

Every answer is preceded by the query read back as coloured English, so a preset button
says what it asked rather than only what came back, and the rows are shown as a table
whose columns are what the query asked for.

Editing a question in the box keeps asking the heading its button came from; a query
typed from scratch asks the current state.

## Driving the run from the viewer

The scene panel's header carries **Pause**, **Restart** and **Loop** whenever a demo
started with `--cramera` is attached (`run_control.py`), alongside a line saying what the
run is doing and which iteration it is on.

- **Pause** freezes the physics simulation where it stands, so the robot stops mid-motion
  and the world can be queried exactly as it is. The sorting thread blocks at its next
  checkpoint too, so nothing new is started while paused. **Resume** starts both again.
- **Restart** abandons the current run and builds a fresh world. It is honoured at the
  next attempt boundary rather than immediately: a plan mid-motion cannot be unwound
  without leaving something half-executed, so a restart pressed during an insertion waits
  for that insertion to finish. An abandoned run is not recorded to the database — it
  sorted only some of its shapes, and a partial iteration alongside complete ones would
  skew every rate computed from them. Pressing Restart while paused resumes first, since
  a paused run never reaches a checkpoint.
- **Loop** keeps building a new world each time a run finishes, until it is turned off.

A single run that finishes with looping off now idles with its world up and its questions
answerable, waiting for either of those buttons — which is what `--iterations 1` without
`--exit-after-sorting` already did, except that the wait can now end in something other
than Ctrl+C.

> Looping runs many iterations in one long-lived process, which is exactly the shape the
> `SIGSEGV` under **Known bugs** below shows up in. For an unattended run of many
> iterations, prefer `batch_runner.py`.

## Known bugs

- **A long-lived multi-iteration process can segfault (`SIGSEGV`, exit code 139)
  before any documented memory limit is reached.** A single `headless_realtime_pacing_runner
  --iterations 5` process crashed partway through its 4th iteration in testing, well
  under the ~130-200MB/iteration RSS growth `batch_runner.py`'s own docstring
  describes needing hundreds of iterations to become a problem. Not yet root-caused
  (likely native code in MuJoCo/Bullet, given the growing RSS and repeated
  world-teardown/rebuild each iteration). Not a data-loss risk -- every iteration up to
  the crash was already committed -- but budget for it: prefer `batch_runner.py` with a
  small `--batch-size` over a single long `--iterations N` process, and be ready to
  resume with `--start-iteration` (see above) rather than expecting one process to run
  to completion unattended.
- **ORMatic mapper configuration can break for the *entire* shared `experiments`
  registry from a single unrelated dataclass**, since `experiments/scripts/generate_orm.py`
  maps every dataclass in the whole `experiments` package into one registry, and
  SQLAlchemy configures that whole registry on first use. A `tuple[SomeType, ...]`
  field anywhere in that package (SQLAlchemy can't use a `tuple` as a mutable
  `collection_class`) will raise `ArgumentError: Type tuple must elect an appender
  method to be a collection class` the first time *any* class in the registry is
  persisted, not just the offending one. This has a real fix already merged, in
  `krrood/ormatic/wrapped_table.py` and `data_access_objects/dao.py` (falls back to
  `list` as the SQLAlchemy-side `collection_class` while keeping the original domain
  type on round-trip) -- but if a `NoDAOFoundForTypeError` or `ArgumentError` about
  collection classes shows up again, run `python scripts/regenerate_all_orm.py` from
  the repository root first, and suspect a *newly added* tuple-typed field elsewhere in
  `experiments` before assuming this module is at fault.
- **Some generated tables can't be created at all**, when ORMatic can't assign a real
  column type to one of their fields (surfaced as SQLAlchemy's `NullType`, e.g.
  `EpisodePlayerDAO.rdr_viewer`'s `RDRCaseViewer` field). `_open_results_session` in
  `franka_montessori_demo.py` skips those tables, and every other table that depends on
  a skipped one through a foreign key (transitively), rather than letting one
  unrelated gap in the huge generated schema stop every table -- including this
  module's own -- from being created.
- **`segmind_event_query_examples.py`'s `exists(var, var == some_list_attribute)`
  pattern silently produces the wrong query** for a many-to-many association list
  (e.g. `attempt.events`): it was observed to run without error but correlate on the
  association target's own `database_id` against the owning row's `database_id`
  directly, rather than joining through the association table -- matching by
  coincidence, not by relationship, on a small dataset where both happened to have the
  same row count. Every query in that module builds its top-level entity fetch with EQL
  but keeps navigation *into* an `attempts`/`events` list in plain Python for exactly
  this reason; a many-to-one attribute chain (e.g. `attempt.plan.database_id`) does not
  have this problem, since it resolves to a real join through an actual foreign key.

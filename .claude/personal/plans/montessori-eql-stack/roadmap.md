# montessori-eql-stack — narrative

## What this stack is

Six stacked PRs on the fork, one strict chain (each branch based on the
previous), turning the Montessori demo into an interactive, queryable, spoken-to
system:

`main` → #169 `montessori_fast_inline_monitor` → #170 `cramera_eql_autocomplete`
→ #164 `montessori_eql_where_is_highlighting` → #165 `montessori_event_replay`
→ #167 `claude/cramera-verbalization-voice-ttwcza`
→ #168 `claude/cramera-voice-questions-ttwcza`

It is registered as native GitHub stack **#173** (created 2026-08-18). The two
`claude/…-ttwcza` branches carry auto-generated session slugs, so their plan
item ids are the readable `cramera-question-readback` / `cramera-voice-questions`
instead of the branch names.

## History that explains the current shape

- **2026-08-18: the stack was re-ordered.** Originally #164→#168 stacked
  directly on `montessori_fast_inline_monitor` (GitHub stack #166), and
  `cramera_eql_autocomplete` (#170) sat beside them in a separate stack (#171:
  #169→#170). The developer asked for the whole montessori chain to be rebased
  onto `cramera_eql_autocomplete`, inserting the autocomplete work underneath
  it. All four branches were rebased and force-pushed; all four tips passed the
  cramera suite (488/540/562/594 tests respectively).
- **The reparent of #164 required dissolving its native GitHub stack** (a base
  change on a stack member 422s): stack #166 was recorded, unstacked, #164
  retargeted, and the stack re-created — then, on the developer's request,
  merged with #171 into the single unified stack #173. The pre-dissolve records
  live in the creating session's scratchpad (`stacks-before-unstack.json`,
  `stacks-before-merge.json`); the procedure is the one in
  `.claude/skills/stacked-pr-maintenance/SKILL.md`.
- **#167 had been stale-stacked** (built on pre-rebase copies of #164/#165
  commits). The restack kept only its two real commits. One semantic conflict
  git could not see: its `test_eql_panel.js` harness binds the panel's free
  variables explicitly and needed an `EqlSuggestions` stub once the
  autocomplete feature sat below it — amended into the harness's own commit.
- **The scenes submodule pin conflict** in #167's "Pin the scenes submodule"
  commit was resolved by keeping the base line's `64b98eda` (public cram-scenes
  main, which already contains the `2230683` that commit originally pinned);
  that commit now only carries its test-skip change and its message is
  slightly stale about the pin.

## Standing conventions

- Per-branch working detail (test baselines, environment landmines, round
  notes) lives in `.claude/personal/pr-progress/<branch>.md` on the
  personal-notes branch — notably
  `pr-progress/cramera_eql_autocomplete.md`, which carries the full
  Round 1–4 history for #170 including the local-environment fixes (lark
  rename, semantic_digital_twin ORM duplicate table, costmaps inflation OOM,
  detector-test reference frames). That mechanism keeps working independently
  of this plan; it is not duplicated here.
- Every PR in this plan is a draft, per the draft-until-told-otherwise
  convention in the personal notes. Both promotions seen so far were undone by
  the pushes that followed: #170 was re-drafted on 2026-08-18 after its main
  merge (its timeline carries no `ready_for_review` event at all, so it had
  been opened non-draft rather than deliberately promoted), and #169 was
  re-drafted the same day after its own CI-fix push.
- Landing order is the stack order; nothing here is parallelizable, which is
  why the plan is one wave / one track with a chained `depends_on`.

## 2026-08-18: the interactive-UI wave

The developer asked for six new items extending the demo once the stack lands
(session: https://claude.ai/code/session_01FqxK37C2yafUeRmJfNGwBZ). They form
a second wave, `interactive-ui`, in three tracks that — unlike the stack — can
run in parallel:

- **Acting from the console** (`action-execution`): first a perform button on
  queried actions, mirroring the replay button #165 gives queried segmind
  events; then running a freshly written, under-specified action with a run
  button. The second item is chained on the first because it reuses the
  execute-from-the-console machinery the first introduces.
- **Annotated event replay** (`replay-annotation`): during replay, the event's
  name rendered in the video with arrows from the label to the involved
  objects, arrow tips following the objects as they move. Depends directly
  on #165's replay.
- **Live tabbed panels** (`live-panels`): the fixed knowledge-graph frame at
  the bottom left becomes a selectable tab widget (the knowledge graph stays
  as one tab). New tabs: a live segmind-event timeline with a moving vertical
  now-bar (depends on #169's monitor for the live detections), then a
  robot-plan-graph tab highlighting the executing node in real time (chained
  on the timeline item because that one introduces the tab container). A
  final item makes every tab detachable/reattachable, freely resizable, and
  maximizable to the full page.

Dependencies are structural (what each item actually needs from the stack),
not a continuation of the strict chain: `montessori_live_event_timeline_tab`
only needs #169, the action and replay items need #165. Branch names are
planned, not yet created; ids equal the planned branch names, following the
stack items' convention.

## 2026-08-18: montessori_live_event_timeline_tab, planned and opened (#175)

Kicked off from `plan.yaml` + this roadmap, based on `montessori_fast_inline_monitor`
(#169), which `check_dependency_readiness.py` reports `open_ready` — open and
non-draft, which this repo's workflow treats as stackable. (#169 is itself
`mergeable_state: dirty` against `main`; that is its own problem, not a blocker for
branching off it.)

### What the item turned out to be

The panel-level tab container is the load-bearing part, not the timeline.
`panels/graph/panel.js` already carries its *own* four-tab bar
(Knowledge / Kinematics / Plan / Statechart), so the new widget cannot be another tab
in there — and `montessori_detachable_panels` ("every tab in the panel widget can be
detached into its own window") only makes sense if a tab holds a whole panel. So the
widget is a container that mounts registered panels as tabs, the knowledge graph
becoming one of them, and the two later `live-panels` items build on that container.

### Decisions taken

- **Events are published per monitor tick, not per finished attempt.** Segmind events
  currently reach `SortingProgress` only in `record_attempt(...)`, so a timeline fed
  from there would fill in bursts seconds apart. `MontessoriEventMonitor.tick()`
  instead notifies a listener with just the events that tick appended, draining into a
  thread-safe append-only log the demo registers with the bridge. Written on the
  planning thread, read by the HTTP thread — the discipline `cramera.live.hooks`
  warns about. `progress.record_attempt(...)` is left alone; the EQL side keeps its
  per-attempt records.
- **cramera defines its own wire dataclass** (`DetectedEvent`) rather than importing
  the demo's `SegmindEventRecord`. The viewer must not depend on the demo — that is
  what `LiveRunControl` / `LiveQuerySource` already exist for, and `live/events.py`
  follows `live/run_control.py` line for line.
- **Timeline geometry lives in `core/timeline_layout.js`**, apart from the panel, for
  the reason `core/split-sizing.js` states in its own header: it keeps the panel down
  to DOM wiring and makes the arithmetic testable without a DOM.
- **The branch keeps its manifest name**, `montessori_live_event_timeline_tab`, rather
  than the session's own designated branch — confirmed with the developer, since every
  dashboard and kickoff link expects the declared name.

### Corrections to earlier notes

- This roadmap's interactive-UI section calls the knowledge-graph frame "bottom left".
  It is the bottom of the **right** column — `config.js` has
  `right: ['eql', 'graph']`, and `core/split-resize.js`'s own comment reads "EQL above
  the graph". Same frame, so no scope change.
- **`montessori_plan_graph_tab` may be partly redundant.** It asks for a tab showing
  the current plan graph with the executing node highlighted live, which
  `panels/graph/panel.js` already provides as its Plan tab, fed from the bridge's
  `/plan` route. Worth re-scoping that item before it starts.

### Landing hazard

`config.js`, `index.html`, `app.css`, `live/bridge.py` and `live/http.py` are also
touched by #165 (`montessori_event_replay`). No duplicated purpose — #165 adds
recording/replay (`live/recording.py`, `web/core/replay.js`, `GET /replay`), neither a
tab container nor a timeline — so this stays its own item rather than folding
into #165. But because this item is deliberately based on #169 and not on #165,
expect textual conflicts in those five files whenever the two meet.

### Session note

Subscribing to tracking issue #174 was blocked by the kickoff session's auto-mode
classifier, so that session does not see structural changes posted there.

## 2026-08-18: #169's conflicts with main resolved

`montessori_fast_inline_monitor` was `mergeable_state: dirty` against `main`
(noted as "its own problem" in the section above). `origin/main` was merged
into the branch and pushed as a fast-forward, `30bd734f..608bc7fe`; the PR now
reports `unstable`, so only CI stands between it and mergeable.

Seven files conflicted, in three groups:

- **Five `ormatic_interface.py` files** (coraplex, experiments, segmind,
  semantic_digital_twin, `test/krrood_test/dataset`). `main` emptied every
  generated ORM interface in #543 and added the `empty-ormatic-interface`
  pre-commit hook; this branch still carried the generated content. Resolved
  to `main`'s empty side, which is the convention `AGENTS.md` now states. CI
  regenerates them for the test runs.
- **`experiments/scripts/generate_orm.py`** — both sides changed the same
  `ORMatic.from_package(...)` call: this branch added
  `segmind.orm.ormatic_interface` to the interface list, `main` replaced the
  empty ignored-classes set with `ignored_classes` (the control-loop
  benchmarking modules). Both kept.
- **`semantic_digital_twin/robots/armar7.py`** — an import-block conflict.
  `main` rewrote the module (adding `Armar7Joint`, importing `OmniDrive`);
  this branch had added `HomogeneousTransformationMatrix`, `Box` and `Scale`
  for the platform collision box its `Armar7MobileBase` builds. Unioned, and
  the branch's duplicate `FieldOfView` import dropped — the module already
  imports it higher up. `pyflakes` reports the merged file clean; the rest of
  the branch's armar7 changes (the collision box, `_get_root_body_name`
  returning `"root"`) auto-merged on top of `main`'s rewrite.

Nothing on the branch referenced the giskardpy behaviour-tree modules `main`
deleted, and the `cramera/scenes` submodule pin came through unchanged at
`64b98eda`.

### The conflict git could not see

The seven textual conflicts were not the whole of it. `giskardpy/executor.py`
auto-merged cleanly and was still broken: `main` had dropped this module's
`typing_extensions.Optional` import along with its last use, while the branch
had added a new `SimulationTimePacer._next_target_time: Optional[float]`. Both
sides were internally consistent, so git merged them without a murmur, and
importing `giskardpy.executor` then raised `NameError: name 'Optional' is not
defined`. `test/conftest.py` imports it transitively through
`coraplex.plans.executables`, so every library's CI job failed at collection —
including `random_events` and `version`, which the merge does not touch. Fixed
in `a5080fd0` by spelling the field `float | None`, as the rest of the module
now does.

Caught by running `pyflakes` over the whole merged tree and subtracting the
findings each parent already had; that difference is empty now. Only five
non-generated files were touched by both sides, and the other four
(`coraplex/plans/executables.py`, `adapters/ros/tf_publisher.py`,
`semantic_digital_twin/exceptions.py`, `test/conftest.py`) merged additively,
with every symbol they reference resolving in the merged tree.

### What CI then found

The merge is also what first gave this branch any CI at all: an unmergeable PR
has no merge ref, so no run had ever happened on it. The first green-ish run
split into three causes, only one of them the merge's own.

- **The merge's own** (`6d944c52`): `_build_pacer` in
  `coraplex/plans/executables.py` built `SimulationPacer(real_time_factor=None)`
  to mean "do not pace". main reworked the `Pacer` hierarchy and gave
  `SimulationPacer` a validating `real_time_factor: float = 1.0`, so the call
  raised `TypeError: '<=' not supported between instances of 'NoneType' and
  'int'`. main states the two cases as pacers of their own, so `_build_pacer`
  now returns `RealTimePacer` or `NoPacing`. This single line was the coraplex
  suite's 175 failures and all four demo jobs. `SimulationTimePacer` also lost
  its own `target_frequency` field, which main's `Pacer` declares `init=False`
  and `Ros2Executor.compile` overwrote anyway.
- **Pre-existing, fixed** (`6d944c52`): `PANDA_SCENE_BODIES_TO_DISCARD` had been
  dropped from `franka_panda_equipment` by 98ac709d while its docstring and its
  importer in `test_franka_panda_equipment` stayed, failing the experiments
  suite at collection; and the segmind detector tests assigned frameless
  matrices to `Connection.origin`, whose setter has required a reference frame
  since before the merge base. Both are the branch's own, exposed only because
  CI finally ran.
- **Pre-existing, left for the developer**: `PickUpAction` has its `AttachNode`
  commented out (8cc3cf69, "demo works now, worth a try"), so main's
  `test_node_expansion` sees three children where it asserts four — restoring it
  would presumably undo whatever that commit was working around, so it is a
  question rather than a fix. And `test_warehouse_storage_layout` /
  `test_wind_farm_service_layout` (added by 08257863) test
  `coraplex_warehouse_storage_demo` and `coraplex_wind_farm_service_demo`, two
  demo directories that were never committed — eight collection errors.

`main` at `e198ea36`, this merge's base, is green, so none of the above is
inherited from the base branch.

### Not done here

The other five stack branches are still based on the pre-merge `30bd734f`, so
the whole chain needs restacking onto the new tip before any of it lands.
`montessori_live_event_timeline_tab` (#175) is based on #169 too and is in the
same position.

### Session note

Subscribing to tracking issue #174 was again blocked by the session's auto-mode
classifier, so this session did not see structural changes posted there either.
The suites could not be run locally: this container has no cram environment
(no `pytest`, no installed workspace packages), so verification was static —
byte-compilation, `pyflakes`, symbol-usage checks, and a `git merge-tree`
against `main` that now comes back clean.

## 2026-08-18: #170 merged cram2/main; the stack above it is now stale twice over

`cramera_eql_autocomplete` (#170) had `cram2/main`'s 23 newer commits merged in and was
force-pushed to `origin` as `03b3130a5` (previous tip `d3321a4e9`). The developer asked
for the conflicts to be resolved toward whichever side is most up to date and proven.

**The one textual conflict** was `Body.has_collision` in
`semantic_digital_twin/world_description/world_entity.py`. Upstream's `208cf0e44` had
independently rewritten the same method: it reads a primitive's `volume` analytically and
still falls back to `shape.mesh.area` for the surface, whereas this branch's `bb75a7157`
had added an analytic `Shape.surface_area` and used it for both. Resolved to upstream's,
for two reasons beyond currency -- the `.. note::` both sides carry (it merged without
conflicting) describes upstream's short-circuit precisely, and upstream shipped collision
tests written against it. Nothing on this branch depended on the other choice.

The cost is that `Shape.surface_area`, five implementations in `geometry.py`, is now
reached only by its own tests in `test_shape.py`. Under AGENTS.md that is a
consult-the-developer call: remove it, or put it back into `has_collision` in upstream's
short-circuit shape.

**A second, invisible conflict** repeated the `giskardpy/executor.py` story this roadmap
records for #169: `main` removed the module's `typing_extensions.Optional` import with its
last use, this branch added `_next_target_time: Optional[float]`, and the two merged
without a murmur into a `NameError` that `test/conftest.py` reaches transitively, breaking
collection everywhere. #169 fixed it in `a5080fd08`; #170 forked from `608bc7fe6`, one
commit earlier, so it arrived here unfixed and got the same `float | None` spelling.

Worth generalising: this class of conflict has now bitten the same file twice. Finding it
is cheap -- `pyflakes` over the merged tree restricted to the files the *upstream* side
touched, since pyflakes is per-file and nothing else can be newly broken. Seventeen files
here, one finding.

**Restacking debt has doubled.** #164, #165, #167 and #168 were already based on #169's
pre-merge tip; they are now also based on #170's pre-merge tip. #175 remains on #169's.
None of that was addressed here -- the developer asked only for this branch.

Once the developer re-authenticated `gh`, #170 was converted back to draft (its
timeline shows it was opened non-draft, never promoted, so the "left ready because I
promoted it myself" exception did not apply) and this dashboard was republished. The
`plan-dashboard` dependencies (`markdown`, `nh3`) were installed to do it.


## 2026-08-18: the whole stack restacked, by merging rather than rebasing

The five branches this roadmap kept listing as "still on the pre-merge tip" are
now all based on their real parents, and every PR in the plan reports
`mergeable: true`. New tips: #170 `cd663196a`, #164 `10ca075c2`, #165
`4d9d9ad33`, #167 `408f4511b`, #168 `5acc3d83f`, #175 `6b8a347fa`.

### Why merge and not rebase

The first attempt followed the Round-4 precedent and rebased. #164 came out
clean — two commits, fifteen files, after dropping `db78bfbc5`, whose ORM
regeneration is dead work now that `main` keeps every generated interface empty
and a hook enforces it. #165 did not. Its history carries stale copies of #164's
two commits *and* internal pre/post-merge duplicates of half its own work
(`Record the running demo`, `Serve the running world's own geometry`, `Pin that
detected events replay`, and a `SymbolGraph` commit all appear twice, on either
side of a merge of the base branch). Replaying that linearly means hand-skipping
six commits and resolving each duplicate against its own earlier self.

So the round merged the new base into each branch instead. It is what these
branches already do — #165 carries three such merges — and it has three
properties rebasing does not: the conflict is resolved once per branch rather
than once per commit, the pushes are fast-forwards so nothing is force-written,
and each PR's diff still comes out as exactly its own work, because merging the
base in makes the base tip the merge base.

The cost is a merge commit per branch, and that the duplicate commits stay in
the history rather than being cleaned out. Worth revisiting if anyone wants
these branches' histories tidied — but that is a separate job from restacking,
and doing it under a restack is what produced the duplicates in the first place.

### The base moved twice during the round

`cramera_eql_autocomplete` was itself one commit behind `#169`, which GitHub
reported as `mergeable_state: dirty` while a local `git merge-tree` said clean.
GitHub was right and the local check was asking the wrong question: it was run
against `a5080fd08`, and #169 had meanwhile advanced to `6d944c52e` with the CI
fixes its own main merge had exposed. Re-running the check against the real tip
reproduced the conflict immediately.

That conflict is worth recording, because both branches had independently fixed
the same bug: the segmind detector tests assigned frameless matrices to
`Connection.origin`. #169 passes `reference_frame=...world.root` at each of the
~30 call sites; #170 had already added a `_move_milk` helper that builds the
origin from `milk.parent_connection.parent`. The two cover an identical set of
thirteen tests, so the helper was kept — one place to change rather than thirty.
`6d944c52e`'s other fixes (the `Pacer` rework in `_build_pacer`,
`PANDA_SCENE_BODIES_TO_DISCARD`) merged without comment and now reach the whole
stack, which previously would have inherited the broken `_build_pacer`.

### Verified

Per tip, cramera suite: #170 477, #164 488, #165 544, #167 566, #168 598, #175
448. Node tests 216/216 on #168 and 183/183 on #175; segmind 46+1 skipped on
#168, 40+1 on #175. Undefined-name scan (`pyflakes` over the files the base side
touched, the check this stack has needed twice) clean on both tips.

Two environment traps worth knowing, both of which look like merge breakage and
are not. Running the suites from a worktree needs the workspace `src` directories
*prepended* to `PYTHONPATH`, not substituted for it — dropping ROS's own entries
turns `test_world.py` into thirteen errors on `ament_index_python`. And any
`segmind` run regenerates `ormatic_interface.py` at collection time; the
committed blobs are all still empty, but the working tree needs reverting
afterwards.

### The has_collision follow-up

The previous section left `Shape.surface_area` reached only by its own tests,
after the conflict resolution took main's `shape.mesh.area`. Resolved by putting
`surface_area` back into `has_collision`, keeping main's short-circuit shape
(volume first, surface second). This is strictly better than either side had:
main's version builds a mesh for exactly the flat shapes the surface threshold
exists for, and a new test forbids mesh building for a flat body to pin that
down. The docstring note, which described the old short-circuit, was updated to
match. `test_world.py` 124 passed, `test_shape.py` 29, `test_spatial_types.py`
234, `test_collision_matrix.py` 30.

### The local lark install regressed again

Round 3's fix was gone from the venv: `lark-parser` 0.12.0 reinstalled, with an
orphaned `site-packages/lark/` holding nothing but `parsers/` shadowing it, so
`from lark import Lark` failed and ROS jazzy's `launch_testing` plugin aborted
collection. Same fix as Round 3 — uninstall `lark-parser`, delete the orphan
`lark`/`lark-stubs` directories, install `lark` (1.3.1). `PYTEST_DISABLE_PLUGIN_
AUTOLOAD=1` is no longer needed. `rapidfuzz` had gone the same way and was
reinstalled; it is correctly declared in `cramera/requirements.txt` on #168.
The repo-side pin was already right both times, so this is purely local rot —
if it comes back a third time, something in this environment is reinstalling
the dead package and that is the thing to find.

## 2026-08-18: the ORMatic bug behind #169's red experiments job

`montessori_fast_inline_monitor`'s `experiments` CI job had been failing at
collection, and the cause was in krrood rather than in the demo. ORMatic decided
a dataclass field gets a plain column by asking `krrood.utils.is_builtin_type`,
which answers "does this type live in the `builtins` module" -- true of every
exception class too. This branch's `InsertionEvidence.raised_exception` and
`CompletedAttempt.raised_exception` are `Optional[BaseException]`, so the
generated `experiments` interface declared an untyped `mapped_column` for them
and SQLAlchemy raised `MappedAnnotationError` on import. Five
`test/experiments_test` modules import that interface at module level, so the
whole suite failed to collect; #170 inherited the same red job.

Fixed in `7a9af9cd0` by naming the types a generated `Mapped[...]` annotation
resolves to a column type for and requiring the field's endpoint to be one of
them. The exception field then falls through to the skip ORMatic already applies
to types it cannot map, which is the right outcome: the persisted record,
`InsertionAttemptRecord.raised_exception`, is a `str` filled from
`named_exception()`, and the two `BaseException` fields are in-flight state.

The shared `is_builtin_type` was deliberately left alone -- `code_generation`
uses it to decide which names need an import, where "lives in builtins" is the
right question. The narrowing belongs to the ORM layer only.

### Why it landed here rather than on #170

The fix was written while debugging `run_montessori_demo` on
`cramera_eql_autocomplete`, but the two `Optional[BaseException]` fields arrive
in this branch's `b47af991b`, and #170 does not touch those files at all. Left
on #170, this branch would have landed with its experiments suite uncollectable.

### Not done here

#170 and everything above it do not have the fix yet; a merge of this branch's
new tip carries it up the stack. Nothing was pushed to `cram2` -- the same
latent krrood bug is on `cram2/main`, reachable by any dataclass field typed
with a builtin SQLAlchemy has no column type for.


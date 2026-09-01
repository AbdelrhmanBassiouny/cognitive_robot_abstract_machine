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

  Both of these were fixed by `9877e5b99` later the same day; see "Both of the
  blockers this roadmap kept listing are already gone" below before treating this
  paragraph as current.

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


## 2026-08-18: main again, and the whole stack restacked behind it

`main` reached `90c241168`, 23 commits past the `e198ea36` #169 had merged that
morning, and #169 went `dirty` again. A `stacked-pr-maintenance` pass reported the
one conflicting file on the pull request, labelled it `needs-resolution` and skipped
it — the pass never resolves a conflict — but it did restack every dependent onto
#169's pre-merge tip `9877e5b99` first, so this round only had to redo that cascade
once the tip moved.

### The conflict was one method, and its answer was already on file

`Body.has_collision`, for the third time this stack has touched it. #169 read
`shape.volume` and `shape.surface_area`; `main`'s `208cf0e4` short-circuits on volume
and then falls back to `shape.mesh.area`. That is the same collision the "has_collision
follow-up" section above records for #170, and the resolution it settled on — main's
short-circuit shape, `surface_area` for the surface, reworded note — was already
sitting on #170 as `73abaf67`. So the merge took #170's file verbatim; the two
branches' copies of `world_entity.py` are now byte-identical.

Its test half came down too, in `f44c76d73`. `main`'s own collision tests cover the
volume short-circuit but not the surface one, so without `forbid_mesh_building` and
`test_flat_shape_needs_no_mesh` #169 would have carried the `surface_area` line with
nothing pinning it — and `test_world.py` would have differed from #170's for no
reason. Bringing them down made both files identical across the two branches, which
is why every merge above #169 came out content-neutral.

### The undefined-name scan, third time

`pyflakes` over the 17 non-generated `.py` files main's side touched, minus each
parent's own findings: nothing new. Compare line numbers stripped, not raw — a
`world_setup` fixture-shadow warning that `main` shifts by a few lines otherwise
shows up eighteen times as a false positive. `giskardpy/executor.py`, the file this
check exists for, merged additively this time; #169 already spelled its field
`float | None`.

### Restacked

`#169 f44c76d73` → `#170 e72937047` → `#164 7d58c8161` → `#165 b76c8ede8` →
`#167 aefd9522d` → `#168 b846d2910`, plus `#175 c97594bc4` off #169 directly. Merged,
not rebased, for the reasons the previous round records. #170 through #168 already
contained both `main` and #169's old tip, so those five merges changed no content at
all — `git diff origin/<branch>..HEAD` empty on each. #175 took `main` for the first
time and came out clean, because #169 now carries the `has_collision` resolution it
would otherwise have hit: a `git merge-tree` before the round predicted exactly that
one conflict on #175 and no other.

Every pull request is mergeable and still a draft; #169's `needs-resolution` label
was cleared once GitHub stopped reporting it dirty.

### Not verified here

No suite was run. This container has no cram workspace — no `sqlalchemy`, no
installed packages, and `test_world.py` needs ROS's `ament_index_python` — so
verification was static: the conflict resolved to a file byte-identical to a tip that
has been tested, `scripts/format_docstrings.py` clean, byte-compilation of everything
the merge touched, the pyflakes differential above, and `git diff` proving each
restacked branch's own diff unchanged. CI on the pushed tips is the real check.

### Both of the blockers this roadmap kept listing are already gone

`9877e5b99` closed them, and it was already the tip when this round started — this
section originally repeated the earlier CI account without rereading the files, and
was wrong on both counts.

`PickUpAction`'s `AttachNode` and `PlacingAction`'s `DetachNode` are back, each
behind `Context.update_world_model_attachment` — the flag all three montessori demos
were already setting and nothing read. And `test_warehouse_storage_layout` /
`test_wind_farm_service_layout` now carry a module-level `skipif` on their demo
directory's absence, following the `PANDA_SCENE_PATH` guard
`test_franka_panda_equipment` already uses, so they skip cleanly instead of erroring
at collection and start running by themselves once
`coraplex_warehouse_storage_demo` and `coraplex_wind_farm_service_demo` land.

The lesson for this roadmap: a "still red, needs the developer" note is a claim about
the current tree, so recheck the file before repeating it. Both of these had been
fixed hours earlier.

### Session note

Subscribing to tracking issue #174 worked this time.

## 2026-08-18: montessori_replay_event_annotations started

Based on `montessori_event_replay` (#165) at 5cf53c5a, on the session's own
designated branch `claude/label-replayed-event-tracking-vj0x2z` rather than the
planned branch name; the manifest records the real branch.

### What the item turned out to be

The replay popup already exists; what it lacks is any knowledge of *what* it is
replaying. A row's replay entry carried only `{start, end}`, so the popup could
name a wall-clock span and nothing else. The work is therefore mostly about
carrying the event through: the answer row's replay entry gains the event's
label and the objects it involved, the popup URL carries both, and the scene
panel turns them into a caption plus one arrow per object, re-aimed every frame
from the objects' live positions in the played-back clip.

### Decisions taken

- **The annotation travels in the popup URL, not through the bridge.** The
  bridge records world states and knows nothing about which event was queried;
  the EQL answer is the only place both facts meet, and the popup is opened from
  there.
- **The demo names its own objects**, through a protocol the query runner
  declares (`InvolvesObjects`), the way `related_highlight_ids` already works -
  cramera must not know what a segmind event is.
- **The caption and arrows are 3D**, like the existing object labels
  (canvas sprites) and highlight arrows (cone meshes), rather than a DOM/SVG
  overlay: the arrow tips then follow the objects with no projection maths, and
  the geometry stays testable in a pure `core/event_annotation.js`.


## 2026-08-18: montessori_perform_queried_action, implemented and opened (#176)

Built directly from `plan.yaml` + this roadmap rather than through
`/plan-item-kickoff`: the session was non-interactive, so plan mode was unavailable.
Based on `montessori_event_replay` (#165), the item's declared dependency, and
restacked onto its post-main-merge tip `b76c8ede8` once the notes branch showed the
base had moved. Pushed as `2dee8f57` and opened as draft #176.

### What the item turned out to be

The load-bearing decision is *how a row says it is an action*. It is the same shape
#165 uses for replay: the entity declares itself by returning a `PerformableAction`
from a `performable_action()` method, and the runner carries one per row **beside**
the rows (`RenderResult.perform`), never inside them - so a viewer that knows nothing
of performing renders the answer unchanged. `CarriesAPerformableAction` sits next to
`CarriesATimestamp` in `query_runner.py` and works the same way.

`PerformableAction` deliberately carries no plan, only a `name` the demo identifies
the action by and a `description` the button says out loud. What the action *is*
stays with the demo, exactly as `LiveRunControl` keeps the meaning of "pause" there.

### Decisions taken

- **The bridge relays, it does not execute.** `LiveActionExecution` mirrors
  `LiveRunControl` line for line: `title()`, `state()`, `perform(name)`, registered
  on the bridge, served at `GET`/`POST /perform`, and announced on `/info` so the
  viewer's existing 3 s poll keeps every button current instead of a poll of its own.
- **A pressed button queues; the sorting thread takes it.** The robot is mid-motion
  when a button is pressed, so `SortingActionExecution` only appends, and
  `_insert_all_shapes` takes requests at the checkpoint *between shapes*. Between
  *attempts* was rejected: an out-of-turn insertion there would interleave with the
  attempt bookkeeping the retry loop is in the middle of writing.
- **A performed insertion stays out of the sort's attempt records.** It is not one of
  the sort's attempts, and entering it as one would count it in every question about
  how the sort is going. `progress.refresh_world_state(...)` runs afterwards, so the
  world-derived half of those records (is_inserted) still answers about the board as
  it stands.
- **`offer()` clears pending requests.** A restarted run replaces every body, so a
  request made against the old world names a shape that no longer exists.
- **The perform preset is live-only**, alongside `_scene_presets()`: the recorded
  bundle answers about a run that is over, so nothing it names can be carried out and
  `presets.json` must not declare it.
- **No action text reaches the markup.** The buttons are emitted empty and identified
  by their position among the buttons; `showPerformState()` gives each its wording
  from `shownActions` and the demo's published state. `esc()` does not escape quotes,
  so putting a demo-supplied description into an attribute would have been an
  injection hole.

### Landing hazard

`live/bridge.py`, `live/http.py`, `web/index.html`, `web/app.css`,
`web/panels/eql/panel.js` and `web/core/answer_table.js` are touched by
`montessori_live_event_timeline_tab` (#175) and by
`montessori_replay_event_annotations` too. No duplicated purpose - this item adds
`/perform`, `core/perform.js` and a perform column - but expect textual conflicts in
those files wherever two of the three meet.

### Environment note

The experiments suite cannot run outside the CI container in a Claude Code on the
web session: `rclpy` is absent (its conftest imports it), `experiments.orm.ormatic_interface`
is empty by design, and `cramera/scenes` is an uninitialised submodule. The new
experiments tests were therefore run with `--noconftest`; the two failures that
remain there (`TestDeclaredBundlePresets`) reproduce identically on the untouched
base, being the missing submodule.

## 2026-08-18: #169 generates the ORM interfaces a run needs

The demo could not be started from a fresh checkout. Every `ormatic_interface.py` is
tracked as an empty placeholder, and an empty module still *imports* - so nothing failed
early, and `ResultsDatabase._schema()` died on `AttributeError: module
'experiments.orm.ormatic_interface' has no attribute 'Base'` a whole world build into
the run.

The fix already existed on `ijcai-tutorial`, in `d65ec4244`, which needed the same thing
for its notebook: the regeneration moved out of `scripts/regenerate_all_orm.py` into the
installed meta-package as `OrmInterface` / `WorkspaceOrmInterfaces`, with
`scripts/regenerate_all_orm.py` and `scripts/protect_generated_orm_interfaces.py` left
as thin CLIs over it. That commit is unchanged on `origin/ijcai-tutorial`'s tip (the
local ref was stale at `49b7744`), and it was ported here verbatim, tests and CI matrix
entry included.

What it was missing is the part this branch needed: it wired the check into the IJCAI
notebook only. Added on top, `WorkspaceOrmInterfaces.ensure_generated()` builds them
only when the checkout has none, `scripts/ensure_orm_interfaces.py` announces the minute
before spending it, and `run_montessori_demo.sh` runs it as a second pre-flight beside
the database one - before the cramera server and the CRAM stack import, so a fresh
checkout pays up front rather than a world build later. A checkout missing one interface
is rebuilt whole, since each generator reads the interfaces of the packages before it.

Verified in this environment rather than statically: `regenerate_all_orm.py` completes
and fills all five interfaces, emptying `segmind`'s and running the new script rebuilds
the workspace back to identical sizes, a second run is instant, and the new suite is
10/10. Pushed as `06582ca32` after rebasing onto `f44c76d73`, which had moved ahead of
the session's start.

### Not covered

`python -m experiments.montessori.franka_montessori_demo` still hits the raw
`AttributeError` on a fresh checkout. Covering it would mean `experiments` importing the
meta-package that depends on it - a dependency cycle - so the honest fix is moving
`orm_interfaces.py` somewhere both can depend on, most likely `krrood`. Left for the
developer to decide.

## 2026-08-18: a second restack, one commit later

`06582ca32` landed on #169 from another session — the ORM-interface pre-flight, plus
a real PR description replacing GitHub's auto-generated one — which made every branch
above it stale again by exactly that commit. The cascade was rerun the same way:
merge the parent in, push, no force.

`#169 06582ca32` → `#170 0e6f0bd32` → `#164 f1bbd6b82` → `#165 07c8cf9c7` →
`#167 04a4f60d5` → `#168 31a649485`, plus `#175 907e92f64` off #169 and
`#176 acc2a1c0a` off #165. All clean, all fast-forward pushes.

`#176` (`claude/queried-action-perform-button-vg2vz3`) was included because it hangs
off #165: it was current before this round and would have been left stale by the very
merge that refreshed its base. The plan's other in-flight `interactive-ui` item,
`montessori_replay_event_annotations`, has no branch on the remote yet, so there was
nothing to restack — but its manifest note still records #165's pre-restack tip
`5cf53c5a` as its base, which that session will want to rebase off `07c8cf9c7`.

Worth noting for anyone reading the tip hashes above: three sessions were pushing to
this stack within the same hour. A restack is only true as of the tip it was run
against, so check ancestry rather than trusting a recorded hash.

### Landed as draft #177

Based on `montessori_event_replay`, so it stacks above #165 rather than on main.
The caption reuses the scene panel's own canvas-sprite name tag (`makeLabel`)
one size up, and the annotation is re-placed inside `applyLive` rather than in
the render loop: the objects only move when a recorded frame is applied, so
following them there costs no extra frames.

Two names had to move: `Replay.label` became `Replay.timeSpan` (a moment now
carries the event's own label, so "label" could not also mean the clip's clock
span), and the panel's `replayWindow` became `replayedMoment`.

## 2026-08-18: the generated ORM interfaces are no longer tracked

The whole workspace was stuck on whichever branch it happened to be on. Every
`ormatic_interface.py` was tracked as an empty placeholder while a working checkout
needs the real, megabyte-sized generated content at that same path, and git refuses to
overwrite a tracked path whose working-tree copy it did not write - so any checkout,
merge, rebase or stash that had to touch one aborted with "your local changes would be
overwritten". Git's skip-worktree bit, which `regenerate_all_orm.py` set on them, hides
the copies from `status` and `add` but does not lift that refusal, so it had never
addressed this. This roadmap's own environment notes had been recording the symptom for
rounds ("revert that churn after coraplex test runs", "any segmind run regenerates
`ormatic_interface.py` at collection time, so revert the working tree afterwards")
without naming the cause.

Fixed on #169 in `232b8ba19` by ignoring the interfaces instead of tracking them. Git no
longer owns the path, so it never has to write it and never refuses; regeneration is
unchanged, and a checkout missing its interfaces still builds them through
`scripts/ensure_orm_interfaces.py`. Verified by switching between #169, #170 and the
612-commit-stale local `main` - which tracks 1.1 MB of generated content and used to be
unreachable - in both directions with the generated interfaces on disk.

The placeholder's machinery went with it: the skip-worktree marking
(`scripts/protect_generated_orm_interfaces.py`), the pre-commit hook that truncated
staged content back to empty (`scripts/empty_generated_orm_interfaces.py`), and
`MissingOrmInterfaceError`, which only existed for a placeholder that had gone missing.
An interface is now simply there or not, so `WorkspaceOrmInterfaces.regenerate` deletes
one rather than emptying it. The CI backstop asks the invariant that now holds - that no
interface is tracked - and the tests pin it for this repository, the five packages'
interfaces and krrood's test dataset alike.

### Restacked, so the whole stack gets it

An existing checkout holds a generated copy at a path the fix deletes, which is exactly
what git will not overwrite, so a branch that still tracks the interfaces stays stuck
until the fix reaches it. All eight dependents were therefore merged onto the new tip in
the same round: `#170 42f3e464c`, `#164 dc28b7d56`, `#165 b8f970a93`, `#167 3964d20eb`,
`#168 c567ee221`, `#175 2d7f7b183`, `#176 7a73346df`, `#177 17b2a07de`. All clean, all
fast-forward pushes, every branch's own diff unchanged - except #177, which was still
based on #165's pre-restack tip and picked up the intervening work as well.

A developer whose clone predates the fix needs the generated copies out of the way once
before the first switch onto a fixed branch; the commit message carries the two commands.

### Same shape, not fixed here

`test.srdf` at the repository root is a tracked file that a test run rewrites in place,
so it blocks a branch switch for the same reason the interfaces did. Left alone: unlike
the interfaces it is a checked-in input, so the fix is to make the test write its output
elsewhere, which is a different change.

## 2026-08-18: montessori_plan_graph_tab, implemented

The developer asked for the item to be implemented directly, and — reading the
"may be partly redundant" note the timeline item left above — to check whether
the plan tab already there works, and to fix or replace it.

### It worked, and it was still the wrong thing

`panels/graph/panel.js` did poll the bridge's `/plan` and colour node rings by
status, so the tab was not broken in the "nothing appears" sense. Three things
were wrong with it:

- **It never said where execution was.** The bridge propagates a running motion
  up the plan tree, so every node from the root down to the running step reads
  `RUNNING`. Colouring the running nodes therefore lights up a whole path and
  points at nothing.
- **The live plan waited on the recorded one.** `showTab('plan')` fetched
  `/api/knowledge/view?name=plan` first and returned early on an error, leaving
  `base['plan']` unset — which is what `liveSource()` reads to decide there is a
  live source at all. On a bundle whose plan view errors, the tab reported that
  error and never showed the running demo, for as long as the page lived.
- **It could not become a tab of the panel widget.** `window.Graph` was a
  singleton bound to one container by `attach()`, so a second panel drawing a
  graph would have taken the first one's canvas — and `montessori_detachable_panels`
  needs a tab to hold a whole panel.

### What was built

The plan tree became `panels/plan_graph`, mounted as a third tab beside Graph
and Events, and the graph panel's Plan tab was dropped (it keeps Knowledge,
Kinematics and Statechart). Decisions worth keeping:

- **The bridge decides which node is being executed, the viewer decides how it
  looks.** `/plan` gained `executing`: the running nodes with no running child.
  `PlanSnapshot.executing` computes it from the serialized tree, so it costs one
  pass over nodes already built and needs no second walk of the plan.
- **`EXECUTING` is a viewer status, not a coraplex one.** `TaskStatusName` mirrors
  what coraplex reports and must keep doing so, so the distinction lives in
  `graph.js`'s `STATUS_STYLE`, alongside the giskardpy life-cycle names it already
  carries. The panel substitutes it for the ids the bridge named, which means the
  in-place re-colour path highlights the moving step without a rebuild.
- **The renderer is created per container.** `GraphView.create(container, legend)`
  replaces `window.Graph` + `attach()`. That also removed the one remaining reader
  of the global, `core/split-resize`'s `refit()`, which now emits `panel:resized`
  on the bus — so every panel drawing a graph re-fits after a drag, not just
  whichever one had attached last.
- **The two sources are independent.** Live polling and the recorded fallback each
  load on their own, which is what makes the second defect above unrepeatable; a
  node test pins it (`a live plan is shown even when the recorded one has no
  backend`).
- **`PlanViewPayload` dropped its `live: "plan"` flag.** Nothing reads it any more:
  the new panel knows its own source, and the graph panel now keys only on
  `live === 'chart'`.

The cramera pytest suite could not run in this session's container — `random_events`
needs its `random_events_lib` C++ extension built from the workspace — so the Python
tests (the three new `executing` cases in `test_live_bridge.py`, the asset checks and
the JS-suite registration) are left to CI. All 205 node tests are green locally.

Opened as draft **#178**, based on #175. Its description carries the three defects
above and the replacement rationale, so a reviewer reading only the PR sees why the
graph panel lost a tab.


## 2026-08-18: the timeline follows the run's clock, then #175 folded into #169

Two rounds in one session, the second at the developer's explicit request.

### The now-bar kept moving while the run was paused

The timeline measured along the wall clock, which knows nothing about pausing. Once a
run had been paused, the bar and the marks behind it no longer meant the same thing: a
mark said where the wall clock had been, the bar said where it is now, and the gap
between them was however long the run had stood still.

`cramera/live/run_clock.py` gives it an axis of its own — `RunClock`, a stopwatch over
one run that stops, resumes and restarts, answering a `RunClockReading` of how far it
has got and whether it is still getting anywhere. `DetectedEvent` carries
`seconds_into_run` and `GET /events` carries `clock: {elapsed, running}`; the panel
carries the reading forward between its one-second polls **only while it says it is
running**, which is the whole of the fix.

`SortingRunControl` drives it, since pausing and restarting is what that class is. One
`_match_clock_to_run()` reads the clock's state off the run's — going exactly when the
run is not paused and is sorting — rather than tracking it alongside, so no transition
can leave the two disagreeing: an iteration rebuilt while paused starts stopped, and a
finished run holds its final reading instead of sweeping on while it idles.

Pointing at a mark now shows what was detected, to what, and when. Wording lives in
`core/event_summary.js`, anchoring in `TimelineLayout.summaryPlacement`. That needed
the plot to stop emptying and refilling itself every 200 ms, which destroys whatever
the pointer is resting on — the `title` tooltip it used to set never had a chance
either. Lanes, marks and the bar are grown into and moved rather than recreated, and a
mark reads `events[index]` when pointed at, so a restart re-purposes what is already
there.

`pytest test/cramera_test` 467 passed (was 448); the experiments run-control,
live-event-source and franka-demo modules 66 passed with `--noconftest`.

### The skip-worktree deadlock, and how it was cleared

The push failed as non-fast-forward, and the pull that would have fixed it aborted on
the six `ormatic_interface.py` files. `232b8ba199` ("Stop tracking the generated ORM
interfaces so branches can be switched") untracks and gitignores them — but git refuses
to merge across a **skip-worktree** path it has to change, and all six still carried the
bit. Worth recording because it is a chicken-and-egg: the very commit that makes the bit
unnecessary cannot be merged in while the bit is set, and emptying the files to match
their committed placeholders does not help — git refuses on the bit, not the content.
The only route is `git update-index --no-skip-worktree` on all six first. Anyone whose
branch predates `232b8ba199` will hit exactly this.

### #175 folded into #169

The developer asked for `montessori_live_event_timeline_tab` to be merged into
`montessori_fast_inline_monitor`, local and remote. The merge **fast-forwarded** — the
timeline branch already contained the whole of its base — so both branches are now the
single commit `f980badc80`, and GitHub closed **#175 as merged** because its head became
its base.

The whole tab-container + timeline feature therefore ships inside #169 rather than as a
PR of its own, and #169's diff against `main` grew by 3081 insertions. The concern was
raised before the merge and the developer went ahead.

**Consequences for the stack**, none of them addressed here:

- #170, #164, #165, #167 and #168 are all based on #169 and inherit the timeline work
  at their next restack.
- **#178 (`montessori_plan_graph_tab`) is based on #175**, which no longer exists as an
  open PR. Its branch `montessori_live_event_timeline_tab` still exists and points at
  the same commit as #169, so nothing is broken yet — but #178 needs reparenting onto
  `montessori_fast_inline_monitor`.

## 2026-08-18: #167's console scrolls, and its words are links at last

The developer reported two things about `cramera-question-readback` from running
the demo: the answer had become unreachable, and the documentation links the item
is named for never appeared at all. Both were fixed on the branch and pushed
(`06a5297b3`, `c045c9f5b`); the pull request description was rewritten to match.

### The answer was pushed out of a panel that clips

The EQL panel is one grid track, `.panel` clips its overflow, and the answer had
`max-height:34%` inside it -- so once the big verbalization and a few rows of presets
sat above it, the answer was simply outside the panel and nothing scrolled. The
question, the presets and the answer now share one scrolling region under the bar.

The bar deliberately stays out of it: the suggestion menu is `position: fixed`,
placed once from the input's own rectangle and never moved again, so a bar that
scrolled would leave its menu hanging in mid-air.

An answered query is scrolled to as well as written. Only a query -- the first
attempt revealed every description written there and left the console showing an
answer nobody asked for on load, because the graph panel emits `entity:select` as
it lays out and the running episode replaces its own step as it goes.

### The links had never worked outside the tests

`DOCUMENTED_PACKAGES` lists the six packages the docs site publishes, and **a scene
is queried through none of them**: the recorded scene's domains are
`cramera.knowledge.entities`, the montessori demo's are `experiments.montessori`.
The resolver was correct and its tests passed against a krrood example class; every
word a real query produced fell through it. Worth remembering as a shape: a test
that proves a mapping works says nothing about whether anything real is in its domain.

`RepositorySourceResolver` answers for the rest, linking a word to the line its class
is declared on, with `WordLinkResolver` asking the published documentation first.

Two things only showed up by running it rather than by testing it:

- **Which revision to read.** `main` would have 404'd for every word -- the `cramera`
  package exists on no main branch at all, only on this stack's own branches. The link
  now reads the file at the commit the checkout is on, which GitHub serves from the
  upstream URL for any commit pushed to a fork of it (verified against the live site).
- **Which checkout.** The first version asked `paths.architecture_root()`, which
  `CRAMERA_ARCHITECTURE` points wherever the knowledge graph should scan -- under the
  test fixture's miniature repository every link vanished again. Split into
  `paths.repository_root()`, the checkout the running code is read from, which
  `architecture_root` now falls back to.

### Not done here

The branch is still based on #165's pre-fold tip, so it has yet to take the timeline
work the #175 fold brought into the stack.

## 2026-08-18: the plan tab was blank because the bridge had no plan

The developer ran the demo and saw the plan tree for a moment at startup and then
nothing. Three defects of the old tab had already been fixed on this branch; this was
a fourth, and it sat a layer lower than any of them.

`GET /plan` was serving an empty tree for the whole run. `Bridge._plan` is set by one
hook, on `Plan.perform` - and the montessori demo never calls it. coraplex's
`execute_single` builds a `Plan`, adds the node, and hands the **node** back; the caller
performs that, and `PlanNode.perform` does not go through `Plan.perform`. So the bridge
watched a method nothing in this demo enters.

What the viewer showed follows from that: the panel draws the recorded plan on load, and
the moment `live:changed` arrives it switches to `/plan`, whose empty node list replaces
the drawn tree with "Attached, but the demo has not started its plan yet." The plan
"appearing for a moment" was the recorded one; the disappearance was the switch.

Fixed by moving the hook to `PlanNode.perform` and reading `node.plan`. That covers
`Plan.perform` too, since it performs its root, so the demos that do call it are
unaffected. `PlanNode` has no subclass overriding `perform`, so one patch reaches every
node.

`Bridge.begin_plan` became `follow_plan`, because the hook now fires per node rather
than once per run: re-entering the plan already being followed returns immediately, and
only a move to a different plan clears `_motion_nodes`. A node outside any plan
(`PlanNode.plan` is optional) is ignored rather than blanking the tree.

### Pinning it

No mimic can catch this class of bug - the wrapper was correct, the method it was
installed on was not. `test_live_hooks.py` therefore drives the plan hook through a real
coraplex plan node: the hooks are installed exactly as `runner.start` installs them, on
a `Bridge` of the test's own, and an empty `SequentialNode` is performed on its own. It
fails against `Plan.perform` and passes against `PlanNode.perform`. That file's "no
coraplex import" convention now carries this one exception, stated in its docstring.

### Also fixed

`test_knowledge_views` had been red since this branch dropped `PlanViewPayload`'s
`live: "plan"` flag - the test still asserted it. The plan panel knows its own live
source now, so the expectation is `None`.

### Environment correction

The roadmap entry above says the cramera pytest suite could not run in this branch's
session. It runs fine in this one: 474 passed. `test_demonstrations.py`'s
`test_spin_thread_ends_quietly_when_somebody_else_ends_the_context` fails in coraplex,
on this branch and on its parent alike, so it is not this work's.

## 2026-08-18: #168 took #167's two fixes, and the conflict was the invisible one

`claude/cramera-voice-questions-ttwcza` merged its base in as `abcb6ee7a`, bringing
down the scrolling console and the source-link fallback #167 had been given that
morning. A fast-forward push; #168 was already a draft, so nothing to re-draft.

Git found one conflict and it was the trivial kind: both branches had appended a
section of tests to the end of `test/cramera_test/js/test_eql_panel.js`, so both
blocks were kept. The harness merged additively on its own — #167's
`scrolledIntoView` counter on the fake elements and #168's `recognizerClass()` /
`speak()` / `mountPanel(overrides, recognizer)` sit side by side without either
side having to know about the other. `app.css` and `test_web_assets.py` likewise:
the two `+45` line counts on `test_web_assets.py` looked like a duplicated change
and were a coincidence, one side's tests landing inside an existing class and the
other's in a new one.

### The one that mattered merged cleanly

#167 introduced `showAnswer(html)` — write the answer, then scroll to it — and
routed the three answer writes in `renderAnswer` through it, deliberately leaving
the four unasked writes alone (load failure, hint, entity description). #168 had
meanwhile added three answer writes of its own on the voice path: the sorry reply,
the matcher's error, and the voice-capture failure. Different lines, different
functions, so git merged them without a word — and every one of them still wrote
straight to `answerEl.innerHTML`.

The result would have been the bug #167 exists to fix, reintroduced on exactly the
path #168 is about: the console now scrolls, so a spoken question's reply is
written below the fold of it and the user watches nothing happen. All three now go
through `showAnswer`. The judgement is #167's own rule read one step further — a
question asked aloud is asked, so its answer is scrolled to like a typed or picked
one; the comment's "Only a query" became "Only what was asked", the unasked
descriptions still being the exception.

The matched path needed nothing: it already runs through `runQuery` → `renderAnswer`.

### Worth generalising

This is the third silent conflict this stack has recorded — after
`giskardpy/executor.py`'s dropped `Optional` import, twice. The shape is the same
every time: one side removes or replaces a way of doing something, the other adds a
new use of the old way, and the two never touch the same line. `pyflakes` catches
the import-shaped one and would not have caught this, because the bypassed function
is a style rule rather than a name error. What did catch it: after any merge, list
every call site of whatever the base side has just centralised
(`grep -n 'answerEl.innerHTML\|showAnswer'`) and ask whether the incoming side
added one that should have been converted.

### Verified

`pytest test/cramera_test` 611 passed (was 598 on this branch, 579 on #167); 221
node tests across 23 files green. The new test
(`a spoken question nothing answers is scrolled to like any other`) was run against
the unfixed panel first and fails there, so it pins the behaviour rather than
describing it.

## 2026-08-18: the plan-graph tab folded into #169 as well

The developer asked for `claude/plan-graph-executing-node-hqkt32` to be merged into
`montessori_fast_inline_monitor`, local and remote - the same fold #175 had already
been given. It **fast-forwarded**, `f980badc80..da2e062e3d`, since the branch already
contained the whole of #169; 23 files, 1399 insertions.

No verification was re-run: a fast-forward leaves the tree byte-identical to the tip
already tested at `da2e062e3d` (474 cramera tests, 234 node tests).

### #178 did not close itself, and #175 did

Worth recording, because the two folds look identical and behave differently. #175's
head branch *was* `montessori_live_event_timeline_tab` and its base was
`montessori_fast_inline_monitor`, so merging head into base made GitHub close it as
merged. #178's base is `montessori_live_event_timeline_tab`, which still points at
`f980badc80` - the work went into a branch that is not #178's base, so GitHub still
sees a diff and #178 stays open as a draft.

`montessori_live_event_timeline_tab` is now a stale pointer: it names the pre-fold
commit of a PR that has already been closed as merged, and it is the only thing keeping
#178 open. Advancing it to `da2e062e3d` would close #178 the way #175 closed; that was
left as the developer's call rather than done as a side effect of the merge they asked
for.

### What #169 now is

It began as "a monitor tick cheap enough to stay on the planning thread" and now also
carries the panel tab container, the live event timeline, the run clock those marks are
plotted against, and the plan-graph tab with its executing-node highlighting - plus the
bridge fix that made the plan tab show anything at all. The five branches stacked above
it inherit all of it at their next restack; none of them has been restacked since.

## 2026-08-18: underspecified queries get a section of their own

The developer asked for a new item: questions that write `...` for an enumerable
field, answered by every value that field could take, offered under a heading of
their own beside Current State and Episodic Memory (session:
https://claude.ai/code/session_01SmNyQsR4yhwF5wGyfrj6sH). Added as item
`montessori_underspecified_queries` in a new `underspecified-queries` track of
the `interactive-ui` wave.

### Why it is based on #170 and not on the stack top

The console has to name a class to build an instance of it, which is exactly
what `cramera_eql_autocomplete` (#170) adds — the workspace class index and the
namespace that resolves a bare class name on first use. Nothing above #170 in
the chain is needed: the where-is highlighting, the recording/replay and the
verbalization work are all unrelated to it. So the item depends on
`cramera_eql_autocomplete` alone, and the branch is based on #170's current tip
`42f3e464`.

### What the item turned out to be

The machinery for it already existed in krrood: a `Match` whose attribute is
`...` is refused by every selective backend and built by
`EntityQueryLanguageGenerativeBackend`, which enumerates an enum-typed open
field over its members and constructs one instance per combination. coraplex's
plan `Context` already resolves its underspecified actions through exactly that
backend. What was missing was a way to *ask* it from the console. So:

- `QueryScope.UNDERSPECIFIED` ("Underspecified Queries") — the panel's grouping
  and the `/presets` scopes payload were already generic, so the section appears
  with no frontend change at all.
- `GenerativeEvaluation` answers a pattern by building it, and anything else
  where it stands — that second half is what makes "and now ask what the values
  were" work.
- `QueryEvaluation.names()` is new: an evaluation can put names in reach of the
  question it answers. `GenerativeEvaluation` puts `generate` there, which hands
  back a variable over what was built, so a follow-up `set_of(...)` selects the
  values the open fields were filled in with. `EqlQueryRunner.names` merges it
  with the source's own `extra_names`, and the bridge now builds one runner for
  both running a query and advertising its vocabulary, so the console offers
  `generate` where it applies.

### Two rendering changes it needed

Both are in `RowRenderer` and both are about answers that were *built*:

- An enum member read back as its member name unless its value is already text
  (`Arms.RIGHT` rendered as `1` before, since `Arms` is an `IntEnum`).
- An instance that names nothing of its own is rendered as its fields alone. It
  used to be titled by its `repr`, which for a constructed action is a paragraph
  of nested dataclass reprs in the answer table's name column.

### The demo's own questions

`MontessoriLiveQuerySource` takes the board it is sorting into and offers
`an(InsertMontessoriShapeAction)(montessori_shape=montessori_shape, board=board,
arm=...)` — the shapes and the board are domains, the arm is what is left open.
The three presets are the pattern itself, the shape/arm pairs that were filled
in, and the same narrowed with `where(... != Arms.BOTH)`. They are deliberately
not in `MONTESSORI_PRESETS`: that list is what the recorded bundle mirrors in
its `presets.json`, and these range over the shapes of a running sort.

Opened as draft **#180**, based on #170. `pytest test/cramera_test` 486 passed and
`test_montessori_live_query.py` 19 passed in the session's container; the rest of
`test/experiments_test` needs generated ORM interfaces and a ROS install it has
neither of, so it is left to CI. Running anything at all there took a Python 3.12
virtualenv built by hand (the repo uses 3.12 syntax, the container ships 3.11) plus
stand-ins for the ROS packages on the import path -- worth knowing for any session
that lands in the same container.

## 2026-08-18: more questions, and a matcher tie-break they exposed

The developer asked for the voice matcher to recognize and answer more questions:
"what is your current goal?", "what is your current action?", "what actions did
you perform?", and "give me all pick up events" for any event type, and likewise
for actions (session: this one, on
`claude/cramera-voice-questions-ttwcza`). The first three are live-only buttons
(the recorded bundle answers about a run that is over); the per-type questions
are written out per ask and matched but never shown as buttons, via the new
`LiveQuerySource.unlisted_presets()` beside `presets()`.

### What the current-action answer needed

An attempt's actions are only recorded once the attempt finishes, so a question
about what the robot is doing now has to read the plan while it performs.
`SortingProgress.follow_plan(plan, shape_key, attempt_number)` holds the
performing attempt, and `actions()` returns the finished attempts' frozen
`PerformedAction`s plus the performing plan's own, with the innermost RUNNING
node marked `is_current` (an expanding action leaves every node down the chain
running). The demo hands the plan over in `_perform_attempt_plan`, right after
`execute_single` and before `node.perform()`.

### The matcher tie-break, and how it was caught

`token_set_ratio` scores any wording that *contains* the asked words at 100, so
"give me all pick up actions" ties with "give me all move and pick up actions"
and lost the tie by list order once the transporting actions were imported. The
matcher's inputs change with what a run has imported, which is why the unit
tests never saw it - only the full experiments suite did, where
`test_montessori_insert_shape_action.py`'s imports sit ahead of the matcher
tests. `QuestionMatcher` now pairs the score with how many words the wording
added beyond the question's own, and prefers the more specific wording on a tie
- the general shape being: a test of one module cannot promise how its
behaviour behaves once the whole workspace is imported, and class-tree-walking
features (here `instantiable_subclasses`) are exactly where import order bites.


## 2026-08-18: the chain restacked from #169 up to #168

The developer asked for the stack to be restacked from `montessori_fast_inline_monitor`
through #168. Only one link had actually broken: #165 was 20 commits behind #164, which
by then carried both the plan-graph fold `da2e062e3d` merged into #169 and the ORM
generation fix `fb0ef552e9` on #170. #169, #170 and #164 were already current with each
other, and `cram2/main` is contained in #169, so nothing upstream had to be merged.

`#165 f9fee84ac` → `#167 f69c5f255` → `#168 d94990922`, merged rather than rebased as
every round before it, and pushed as fast-forwards. Only the first merge conflicted, all
three keep-both:

- `live/bridge.py`: each side had added an import (`DemoRecording`, `LiveEventSource`).
- `config.js`: #165's `?replay=` popup layout against the tab container's
  Graph/Events/Plan tabs. The popup keeps the scene alone; every other page gets the
  tabbed right column.
- `test_split_resize.js`: the incoming side returned `eql` and `graph` from `install()`,
  which #165's rewrite had deleted — it builds its panels from `rightPanelIds` now, so
  taking that side verbatim would have been a `ReferenceError`. Kept #165's shape plus
  the `emitted` field the tab work's one `panel:resized` test reads.

The silent-conflict check the stack has needed four times found nothing: no reference to
the removed `window.Graph`/`attach()` survived anywhere, and every answer write on the
voice path still goes through #167's `showAnswer`.

Verified per tip: cramera 587 / 622 / 663, node tests 281 / 295 / 309, all green. All six
pull requests report `MERGEABLE`, all still drafts, bases intact.

### Left stale by this round

`#176` and `#177` both hang off `montessori_event_replay` and were not restacked — the
request stopped at #168. `#178` is still based on `montessori_live_event_timeline_tab`,
the stale pointer the plan-graph fold left behind.

### Environment

The `.venv` in the checkout is not the project interpreter and has rotted well past the
lark landmine this file keeps recording — `objgraph` is gone from it too, so
`test/conftest.py` cannot even be imported there. `~/.virtualenvs/cram`, which `.idea`
names as the project SDK, runs everything cleanly with no `PYTEST_DISABLE_PLUGIN_AUTOLOAD`.
Note that `~/.virtualenvs/cram2` has `cramera` installed from a *different* checkout
(`Projects/copied/...`), so a suite run there tests the wrong tree.

## 2026-08-18: a read-only results database must still answer the episodic queries

The developer queried the episodic database from the running demo and got
`permission denied for schema public` on a `CREATE TABLE` — `ResultsDatabase.open_session`
prepared the database before reading it, and preparing issues a `CREATE TABLE` for every
table the generated schema knows of but the database lacks. The database in question was
the shared one: `FRANKA_MONTESSORI_SORTING_DATABASE_URI` is set in `~/.bashrc` to
`localhost:5433`, an ssh tunnel to a remote PostgreSQL 17 whose
`semantic_digital_twin_readonly` role has USAGE only on `public` (the local 5432 cluster
is writable but holds a tenth of the rows). The record path already degraded — the
pre-flight's `verify_writable` fails, `open_recording` returns `RecordsNothing` — only
the query path crashed, because the branch's regenerated schema has tables the remote
database predates.

`open_session` gained a keyword-only `create_missing_tables`, and the episodic-memory
evaluation asks for sessions with it false: reading what a database holds must not
demand the right to add to it. Recording keeps preparing, and every other caller keeps
the default. Two tests pin it, both verified to fail without the fix: the unit-level
`test_a_session_can_be_opened_without_preparing_missing_tables` (a SQLite file reopened
`mode=ro` with one table dropped, so creation would genuinely have been attempted) and
the end-to-end `TestAnsweringFromAReadOnlyDatabase`, which asks the success-rate preset
through `MontessoriLiveQuerySource` against such a database. The first version of the
end-to-end test passed without the fix and had to be strengthened: the fixture database
already held every table, so `create_all`'s checkfirst had nothing to create and the
read-only refusal never fired — a test must leave the database missing the thing whose
creation is being refused.

Committed and pushed as 22845f77b; the PR description gained a matching section. The
three database test files run here: 52 passed, the one failure being the known
`presets.json` submodule drift. Left open: whether the mocks (`_MockedConvexSetDAO` and
its association table) belong in the production `experiments` ORM interface at all, and
whether this fix deserves its own bug-fix PR instead of riding #168 — it touches
`results_database.py`, which the voice-questions work otherwise leaves alone.

## 2026-09-01: #169 merged main again, and main had built the same things

`montessori_fast_inline_monitor` had gone thirteen days without a push while `main`
reached `1227a68f`, 353 commits past the `90c24116` it last carried. Nine
`stacked-pr-maintenance` passes had reported the conflict on the pull request and
skipped the branch, the `needs-resolution` label doing exactly what it is for. Merged as
`3e9f3847`, a fast-forward push; the pull request went from `dirty` to `unstable`, so
only CI stands between it and mergeable.

Twenty-five files conflicted, and the interesting thing about them is how many were
collisions of purpose rather than of text: `main` had independently built three things
this branch built.

### The ORM interfaces: main's is the superset

`main` ported the same `ijcai-tutorial` `OrmInterface` / `WorkspaceOrmInterfaces` this
branch had, and then carried it much further -- 1,927 lines against this branch's ~400.
It asks whether an interface is *outdated* against the sources it is generated from
rather than merely whether it is present, runs every generator in one interpreter
through a new `orm_generation` module, shows a progress bar, and gives pytest an
`--orm-build` option so a test run builds what it needs. Both sides had already deleted
the placeholder machinery (`empty_generated_orm_interfaces.py`,
`protect_generated_orm_interfaces.py`) and both gitignore the interfaces.

So `main`'s side was taken whole, and with it the disappearance of
`WorkspaceOrmInterfaces.ensure_generated`. What it does not cover is a run that is not a
test run, which is the only reason this branch's piece existed:
`scripts/ensure_orm_interfaces.py` stays as `run_montessori_demo.sh`'s pre-flight,
rewritten as a thin CLI over `is_outdated` + `regenerate`, exactly as
`regenerate_all_orm.py` is a thin CLI over `regenerate`. `doc/contributing.rst` says so
beside `main`'s own `--orm-build` section. The explicit "Build ORM" CI step went too:
`main` builds through the conftests instead.

### The bounding boxes: a rename over an invasive type change

`main` renamed `BoundingBox` to `VolumetricBoundingBox`, added `PlanarBoundingBox` for
floor-plan regions, and factored what they share into an `AxisAlignedBox` base -- which
had *absorbed this branch's own additions*, `Bounds`, `to_array_bounds` and
`from_array_bounds`, in a form generic over dimensionality. Meanwhile this branch had
changed the same class's `origin` from a `HomogeneousTransformationMatrix` to a
`NumericTransform`, which is the whole point of the monitor work: a box that carries
numbers can be read off the thread that owns the world.

The question the merge had to answer was where that numeric origin lives now that there
are two box classes. It went onto the base: `AxisAlignedBox.__post_init__` reads a
symbolic origin out into a `NumericTransform`, so `PlanarBoundingBox` gets it too, and
`transform_to_origin` crosses frames through `compute_forward_kinematics_np` over
corners built from a new abstract `axis_bounds`, replacing `main`'s symbolic version for
both dimensionalities. The alternative -- numeric on the volumetric box only, symbolic on
the planar one -- would have left two behaviours under one name in a family whose base
class exists precisely to state one.

Judged in scope rather than a scope change: "a bounding box carries numbers, not CasADi"
is a decision this pull request already shipped and describes. `main` factoring a base
class out of the class that carried it does not reopen it.

Two things fell out of that. `axis_intervals` and `origin_translation`, which this branch
added to read a *symbolic* origin once instead of three times, are gone: with a numeric
origin `main`'s per-axis `_interval` already costs nothing, so keeping them would have
been a second name for one operation. And both `__eq__` implementations were compared
with `np.allclose(self.origin, other.origin)`, which has no array to work with once an
origin is a `NumericTransform` -- latent on this branch since the type changed, and newly
reachable for `PlanarBoundingBox`. They compare `origin.to_np()` now, pinned by two tests
written to fail first.

### MuJoCo syncing: both sides rewrote the same layer

`main` resolved each connection to its joint once through a `JointBackedConnection` and
moved the world -> sim push under the model lock, because RK4 writes integrated qpos back
at the end of a step and silently swallows anything written mid-step. This branch had
added ramped control setpoints, physically simulated DOFs and an integrated position
setpoint. `main`'s structure was taken and the ramping kept on top; the command interval
the ramp divides by is now measured in `_measure_command_interval` immediately before the
push, which is where this branch's own inline loop measured it.

The keyframe qpos stayed this branch's `_compute_keyframe_qpos`. `main`'s version walks
`world.bodies_topologically_sorted`; this branch's walks the *compiled model's* own joint
order, and its docstring records why -- the two orders do not generally match, and getting
it wrong assigns one body's qpos to another silently.

### The rest

`PickUpAction` and `PlacingAction` take `main`'s pose thresholds, `perceive_before_grasp`
and `object_designator.root` target pose while still gating `AttachNode`/`DetachNode` on
`Context.update_world_model_attachment`. `Armar7MobileBase` no longer takes `forward_axis`
as a constructor argument -- `main` made it a `classproperty` -- and both sides root it at
`Dummy_Platform_link`. krrood's two tuple-collection fixes, which both sides had written
differently, went to `main`'s wording; the branch's own `COLUMN_VALUE_TYPES` ORMatic fix
auto-merged and survives, since `main` does not have it. The experiments conftest took
`main`'s renamed `CEREAL_NAME` beside this branch's `create_engine` import. Both sides had
appended tests to the end of `test_multi_sim.py`; both blocks were kept.

### Verified statically only

This container has no CRAM workspace -- no numpy, no sqlalchemy, no ROS, and Python 3.11
where the repository needs 3.12 -- so no suite ran. What was checked: every resolved file
byte-compiles under 3.12, `scripts/format_docstrings.py` clean, `git merge-tree` against
`main` clean, and the undefined-name differential this stack has now needed five times --
`pyflakes` over the 258 non-generated `.py` files `main`'s side touched, minus each
parent's own findings, comparing with line numbers *and* "from line N" back-references
stripped, which is what turns the `Color` re-definitions from eight false positives into
none. Nothing new. CI on `3e9f3847` is the real check.

### Not done here

The five branches stacked above this one, plus #176, #177 and #178, are all stale by this
merge. Nothing was restacked: that is `stacked-pr-maintenance`'s pass and it was not asked
for.

`cramera` still declares its dependencies through `cramera/requirements.txt`, the
convention `main` has just replaced everywhere else with inline `pyproject` dependencies
(it deleted fourteen such files). It is valid setuptools and installs, so it was left
alone -- converting it would conflict with #168, which declares `rapidfuzz` there.

The `needs-resolution` label is still on the pull request; the routine that applies it
clears it on its next pass now that the branch merges cleanly.

## 2026-09-01: what CI said about the main merge

`3e9f3847` was pushed with only static verification behind it, and CI came back red in
six jobs. Fixed in `82a2c0a8e`. Three of the four causes were the merge's own, and all
three are the same shape: `main` moved something, the auto-merge kept the branch's use
of where it used to be, and `git` said nothing.

- **`insert_shape_action.py` called two things that had moved.**
  `translate_free_space_to_where_condition` became
  `GraphOfBoundingBoxes.constrain_to_free_space` (`1a6d4206e`), which attaches the
  condition to the variable's own query rather than returning it, and
  `navigation_map_at_target` became a classmethod of `PlanarGraphOfBoundingBoxes`. The
  first killed three montessori test modules at import. Ported the way `main` ported
  its own caller in `sage10k_actions.py`, including the third thing that commit fixed
  there and this file also had: a planar map asked for a node by a full 3D position
  rather than by the pose's floor-plane projection.
- **`PickUpAction` passed a view where a body was wanted.** `main` made
  `object_designator` a view and took `.root` at every use; this branch's
  `grasped_object=self.object_designator` was added after that and was missed in the
  resolution, so both coraplex demo jobs died on `'Milk' object has no attribute
  'collision'`.
- **The `experiments` ORM interface lost a declared dependency.** Taking `main`'s
  `WORKSPACE_ORM_INTERFACES` whole dropped `segmind`, which this branch's generator
  imports, and `main`'s own `test_declared_dependencies_are_the_ones_the_generator_imports`
  caught it.

The fourth was **the thing this merge decided not to do**. `cramera` resolved its
dependencies from a `requirements.txt`; the merge left it alone as "valid setuptools,
so not worth conflicting with #168". `main` had landed
`test_dependency_declarations.py`, which fails exactly that. It declares them inline
now, `experiments` declares the `cramera` and `segmind` it imports, and the
requirements file is gone. The lesson is narrow and worth keeping: a convention `main`
has moved to is a convention `main` may be testing, so the check for "is the old way
still allowed" is to look for a test of it, not to reason about whether it still works.

Three more failures were the branch's own, red before the merge and left red by it:
`apply_grasp_contact_parameters` has taken a `friction` argument since `72a9c186d`
while its two tests still called it without one, `MontessoriLiveEventSource` has taken
the run's clock since the timeline work while one of its tests still built it without
one, and two test processes reaching `parse_panda` at once downloaded the same mesh
into the same directory under one temporary name, so whichever renamed first took the
file out from under the other. All three fixed; the mesh one is pinned by two tests
verified to fail against the shared name.

### The check the pyflakes differential was missing

`pyflakes` is per-file, so it sees an undefined *name* and never sees that
`from x import y` names something `x` does not define. That is precisely the shape of
the `insert_shape_action` breakage, and of the two `giskardpy/executor.py` rounds this
roadmap already records -- the import-shaped ones happened to be caught only because
the *use* was also undefined in the same file.

The differential now has a second half: parse every
`from <workspace module> import <name>` in the tree, resolve the module to its file,
and report a name that file does not define, following `import *` re-exports through
`__init__.py`. Run against the merge and against the branch before it, the two sets
come out identical -- 41 findings either way, all long-standing (generated segmind
SCRDR model files, and ROS shims the resolver cannot see through). The signal is the
*difference*, exactly as with pyflakes.

### Still red, and not this merge's

`test_shape_falling_through_its_hole_is_detected_as_pick_up_and_insertion` writes a
frameless `HomogeneousTransformationMatrix` into a connection origin whose setter has
required a reference frame since before the merge base. It is the one failure this
roadmap has recorded as pre-existing for many rounds, it reproduces on
`stutter_montessori`, and chasing it needs the workspace this container does not have.
Left alone rather than guessed at.

## 2026-09-01: the long-standing falling-shape failure was one missing frame

The section above left
`test_shape_falling_through_its_hole_is_detected_as_pick_up_and_insertion` red as
"needs the workspace to chase". The developer asked for it fixed, skipped or xfailed,
and it turned out to need none of those three as a judgement call: the cause is in the
test and it is a single argument.

`move_to` assigned a frameless `HomogeneousTransformationMatrix` to the shape's
connection origin. That setter transforms the value into the connection's parent frame
and therefore has to be told which frame it is in, so the *first* call raised
`MissingReferenceFrameError` -- the test never reached the movement it exists to
exercise, and its three assertions had not run in a long time. It reproduced on
`stutter_montessori` because the setter's requirement predates both branches.

Which frame is not a guess. The coordinates are read off `global_transform` two lines
above, so they are the world root's; and the world root is also the connection's
parent, because `MontessoriWorld._spawn_free_body` joints a movable shape straight to
`world.root` and writes its own origin with `reference_frame=self.world.root`. Stating
it transforms through an identity, so the poses the test means are unchanged --
which is what makes the fix safe to push from a container that cannot run it.

`085f160f9`. Whether the assertions themselves hold is now a real question for the
first time, and CI answers it rather than this session.
## 2026-09-01: the second CI round -- a retyped designator and a world budget

Two jobs stayed red after `82a2c0a8e`, and neither was a leftover of the first CI round.

### `PickUpAction` names its object by annotation now

Eight `experiments` tests died on `'Body' object has no attribute 'root'`. `main` had
retyped `PickUpAction.object_designator` (and `ReachAction`'s) from `Body` to
`HasRootBody` and taken `.root` at every use inside the action; the montessori callers,
written against the old type, were handing it `self.montessori_shape.root`, so the
action called `.root` on a `Body`. They pass the annotation itself now, which is what
`main`'s own callers (`cereal`, `apple_annotation`) do. `PlaceAction` still takes a
`Body`, so the two `PlaceAction` sites four lines below each fix keep their `.root` --
the shape of the bug is exactly that two neighbouring calls no longer want the same
thing.

Worth recording as a correction: the first CI round fixed the *reverse* of this in
`pick_up.py` (`grasped_object=self.object_designator` -> `.root`). Both are right. The
field is a view now, so uses inside the action need `.root` and callers must not
pre-apply it -- one type change producing errors in opposite directions on either side
of the boundary.

The same call site exists in the two Franka pickup smoke-test scripts, neither of which
CI runs. `franka_pickup_smoke_test.py` already had a `MontessoriShape` in hand. The
bare one deliberately builds an unannotated cube -- but "bare" in its docstring is about
the scene carrying no sorting board, not about semantics, and naming an object to
`PickUpAction` now requires an annotation, so the cube is annotated as the `CubeShape`
the sorting demo picks up.

### The world budget, and why it only surfaced now

`semantic_digital_twin` tripped `count_worlds`, `test/conftest.py`'s autouse guard that
fails a module once `objgraph.count("World") > 30` after a `gc.collect()`. It is a
budget shared by the whole run, checked at every module boundary, and the suite runs
under `-n auto`, so which worker crosses it depends on how xdist distributes modules --
which is why exactly one module reported it.

The branch's contribution to that budget was found by elimination rather than guessed:
of every fixture in `test/conftest.py`, `armar7_world_state_reset` is the **only** one
that any `test/semantic_digital_twin_test` file requests on this branch and none does on
`main`. `_armar7_world_setup` behind it has no user anywhere on `main` at all, so main's
sdt job never builds an Armar7 world and this branch's does -- and holds it for the
whole session. `test_world_armar7.py`'s second test mutates the drive origin, which is
the only reason it wanted the deepcopy-and-restore wrapper; a world built per test is
served better, so it takes one and the session holds none. Nothing it asserts changed.

Why it took until now to appear: the sdt suite had **never run on this branch**. Every
run back to `da2e062e3` failed at the `Build ORM` step and skipped `Run tests` outright;
the main merge is what brought the ORM machinery that makes the job get as far as
pytest. So this is not a regression the merge introduced but a suite addition that had
never been measured.

The honest limit on this one: the fix is reasoned, not measured. This container has no
CRAM workspace, so nothing could count worlds. The reasoning is exact about *what the
branch adds* (one session-held world, and nothing else) but not about how close main's
own baseline sits to 30. CI is the check.

## 2026-09-01: the six-hour coraplex job was an unbounded tick loop

The developer reported the coraplex and examples jobs running for hours. They were not
slow: `test_each_lib (coraplex)` had been starting, producing nothing, and being killed
by GitHub's six-hour job limit on every push since the main merge. The workflows declare
no `concurrency` group, so each superseded run kept burning a runner for its full six
hours; six of them were cancelled by hand.

The log names the hang exactly. `test_training_environments.py::test_move_to_reach`
starts on `gw1` at 07:56:55 and never reports again; `gw0` drains its own queue by
07:57:15 and the session waits on `gw1` until cancellation. That test is `main`'s,
untouched by this branch: it asks `MoveToReachTrainingEnvironment` for two randomly
sampled episodes and asserts only `success_rate >= 0.0`, precisely because some sampled
targets are unreachable and are *expected* to fail.

What turns an unreachable target into a failure rather than a hang is the tick budget,
and this branch had removed it. `main` ticks
`while counter < len(self.motion_mappings) * 2000` and then raises `MotionDidNotFinish`.
Making that budget configurable here spelled its default `None` and read `None` as "tick
until the motion ends" -- so every caller that did not ask for a budget got `while True`.
The only callers that ask are the three montessori scripts; the whole coraplex suite,
and every other consumer, ran unbounded.

`d21071ca5` makes the budget a number again, defaulting to the 2000 `main` hardcoded and
now named `DEFAULT_MAX_TICKS_PER_MOTION_MAPPING`, and deletes the `None`-means-unbounded
path so no configuration can produce a non-terminating loop. `ExecutionEnvironment`'s own
`max_ticks_per_motion_mapping` keeps meaning "leave the budget unchanged", which is a
different thing and stays `Optional`. The bound moved onto a `tick_limit` property so the
loop and the test that pins it read one statement of it.

### Why the test is on the bound rather than on the hang

The behaviour is "a motion that never ends gives up", but exercising that with the
default budget means 4000 ticks of a real QP solve. Worse, a test that *sets* a small
budget passes against the broken code too, since the bug is only in the default. So the
test asserts what actually regressed: with no environment budget set, `tick_limit` is
finite and equals `len(motion_mappings) * DEFAULT_MAX_TICKS_PER_MOTION_MAPPING`. A second
test pins that an environment's budget replaces the default and is restored on exit.

### The same shape, left alone

`SimulationTimePacer.sleep()` (`giskardpy/executor.py`, added by this branch) spins
`while self.simulation_clock() < self._next_target_time` with no bound, so a stalled
simulation clock blocks a tick forever and the tick budget above cannot help. It is not
reachable from any test -- only the three montessori demo scripts set
`context.simulation_clock` -- so it is not what CI was hitting, but it is a real hang in
the demo. Left for the developer: what a stalled simulation should do is a policy
decision, not a fix to guess at.

### Environment

Still no CRAM workspace, so neither the fix nor its tests could be run: verified by
byte-compilation, a pyflakes differential (no new findings), and reading `main`'s own
version of the loop. CI on `d21071ca5` is the check.

## 2026-09-01: one gripper bug behind two failures and the demo hang

With the tick loop bounded, the coraplex job finished for the first time since the main
merge -- 14:46, 3 failed / 415 passed -- and `test_move_to_reach`, the test that had been
hanging, passed. The Tracy *demo* job went on hanging, because it runs
`ExecutionType.REAL` and `_execute_real` hands the motion to giskard and waits, with no
budget of its own.

Two of the three failures and that hang are the same bug.
`MoveGripperMotion._goal_state` measures the grasped object's half-width in meters and
assigns it to every finger connection. That is exactly what the Panda's model means: its
fingers are `type="slide" range="0 0.04"` prismatic joints sliding along the very axis
the width is measured along, closed at `0.0` and open at `0.04`. No other gripper in this
workspace says that:

- **Tracy** (Robotiq 85): open `[0.0, 0.0]`, closed `[0.8, -0.8]` -- revolute knuckles in
  radians, and antisymmetric. The sizing commanded *both* knuckles the same small
  positive number, which is neither the right unit nor the right sign, so `CloseGripper`
  could not converge. Simulated, that became `MotionDidNotFinish` once the tick bound
  existed; on the real path it is an unbounded wait inside giskard, which is the demo
  hang.
- **PR2**: open `[0.548, 0.548]`, closed `[0.0, 0.0]` -- the Panda's *sign* convention
  but in radians. Wrong in the same way and quieter about it: the number lands inside
  the joint's range, so the motion converges, just to a meaningless angle. Nothing
  caught it because the only test of the feature asserted the convergence *threshold*
  rather than the goal.

So the sizing now applies only where every finger connection is a `PrismaticConnection`
-- the property that makes a width in meters the thing a joint position means. It is the
joint type, not an inference from the numbers. Every other gripper keeps the fully-closed
goal its own model states, which is what it had before the feature existed and what
`main` still does, where this job passes.

One predicate (`_sizes_goal_to_object`) now decides both the goal and the tightened
convergence threshold. They were computed independently before, so a fallback in one
would have left the other tightened against a goal that had not been resized.

The PR2 test was retargeted rather than deleted: it asserts the new contract (a revolute
gripper keeps its nominal closed goal) instead of the threshold. Worth knowing that the
tight-threshold behaviour is now pinned only end-to-end, by the montessori Panda suite --
coraplex has no prismatic gripper to test it against.

### The third failure was a TDD cycle that was never finished

`test_spin_thread_ends_quietly_when_somebody_else_ends_the_context` arrived in `08257863`
and `git diff origin/main...HEAD -- coraplex/src/coraplex/demonstrations.py` is *empty*:
the test was added and the fix it describes never was, so it has never passed. (An
earlier note in this roadmap recorded it as failing "on this branch and its parent
alike, so it is not this work's" -- true but misleading, since the parent is another
branch of this same stack.) The spin thread ran `executor.spin` directly; rclpy reports
a context ended by its owner -- the ordinary way a borrowed session stops -- by raising
`ExternalShutdownException` out of the spin and, unlike the executor's own shutdown,
does not swallow it. `_spin_until_the_context_ends` ends the thread quietly on it.

### Worth keeping

- A demo on the real-execution path has no tick budget: `_execute_real` is one call into
  giskard. The budget added for `_execute_simulation` does not protect it, which is why
  the Tracy demo kept hanging after the bound landed.
- Read a gripper's own `GripperState` joint states before assuming what its numbers mean.
  Three grippers here use three different conventions, and two of them look alike.

## 2026-09-01: the library half of #169 split into #244, and #169 re-based onto it

At the developer's request, everything #169 changes under `semantic_digital_twin`, `segmind` and
`krrood` - with the one `physics_simulators` change the Mujoco adapter's real-time factor needs,
and the Armar7 fixtures in `test/conftest.py` the new sdt tests use - is now its own pull request,
#244 (`sdt_segmind_krrood_from_fast_monitor`), off `main`. It was cut by checking those paths out
of #169's tip `daeddaf6` onto `main`, three commits, one per package, so `git diff` between the two
branches over those paths is empty and re-basing #169 onto it changes nothing in its tree. #169's
diff now shows the cramera, experiments, coraplex and giskardpy work alone. Left in #169
deliberately: `giskardpy`'s `SimulationTimePacer`, which only cramera and the demo scripts use, and
the `experiments` ORM interface declaration.

Re-basing #169 took the native-stack procedure `stacked-pr-maintenance` records: the base change
was refused with `422 - Cannot change the base branch because the pull request is part of a stack`,
so stack #173 (`169, 170, 164, 165, 167, 168`) was recorded, dissolved, #169 retargeted through the
MCP `update_pull_request`, and the stack re-created as **#247** with #244 at its foot:
`244, 169, 170, 164, 165, 167, 168`. The pre-dissolve record is in the creating session's scratchpad
(`stacks-before-unstack.json`). The `knowledge-directed-perception` item
`episode-replayed-into-the-world` (#246) is based on #244 as well, by the same instruction, so the
segmind detector changes sit under the rosbag player rather than colliding with it later.

Landing hazard for #244: #229 (`sdt_predicates_answer_whether_they_hold`) rewrites
`reasoning/predicates.py` and edits `world_description/geometry.py`, both changed by #244; whichever
lands second takes the other's structure and keeps the bounds rejection and the numeric containment
ratio on top.

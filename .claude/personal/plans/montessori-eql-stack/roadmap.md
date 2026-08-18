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

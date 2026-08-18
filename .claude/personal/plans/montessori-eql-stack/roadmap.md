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
- PRs #169 and #170 are ready-for-review; #164–#168 are drafts, per the
  draft-until-told-otherwise convention in the personal notes.
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

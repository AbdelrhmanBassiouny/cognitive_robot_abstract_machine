# cramera — CRAM Visualization

Browser-based visualization for the CRAM architecture — one tool for two modes:

- **Recorded**: run any coraplex demo once through the onboarder and get a
  lightweight, self-contained 3D scene (URDFs + meshes + the real recorded
  giskardpy trajectory) that plays in any browser, no ROS required.
- **Live** (RViz replacement): attach the viewer to a *running* demo — it
  renders the executing world in real time, and dragging objects in the viewer
  writes their pose back into the demo's world.

## Quick start

```bash
cramera                                  # serves http://localhost:8711
cramera-onboard path/to/demo.py --name my_scene    # record a demo once
cramera-live path/to/demo.py             # run a demo with the live bridge
```

Scene bundles are **generated artifacts** (tens of MB per scene) and are not
part of this repository — ready-made demo recordings live in
[cram2/cram-scenes](https://github.com/cram2/cram-scenes), wired as an
**optional** submodule:

```bash
git submodule update --init cramera/scenes    # ready-made demo scenes (optional)
```

The viewer looks for bundles in this order: `CRAMERA_SCENES=/path` (env
override) → the initialized submodule `cramera/scenes` → `~/.cramera/scenes`
(where the onboarder writes by default). Live visualization and freshly
onboarded scenes need none of the ready-made bundles. Select a scene with
`?scene=<name>` or `CRAMERA_SCENE=<name>`.

## Live mode

Two ways to attach the live bridge to a running coraplex demo:

1. As the run wrapper (e.g. a PyCharm run configuration):

   ```bash
   cramera-live path/to/demo.py
   ```

2. As a one-liner at the top of a demo file:

   ```python
   from cramera.live.runner import start; start()
   ```

Either way an HTTP bridge starts on port 8765 (`LIVE_VIZ_PORT` to change);
while it is reachable the viewer shows a *Live* button that renders the
running world instead of the recording, and dragging an object writes its
pose back into the demo's world.

### Asking the running demo questions

A demo can also answer EQL queries about itself. It registers what it wants
asked about:

```python
from cramera.live.bridge import BRIDGE
BRIDGE.register_query_source(MyDemoQuerySource(...))
```

A query source implements `cramera.live.query.LiveQuerySource`: a `title()`,
the `presets()` to offer as buttons, and the `knowledge()` it offers to be
questioned about.

A demo usually knows more than one thing, so `knowledge()` returns one
`QueryableKnowledge` per `QueryScope` — `CURRENT_STATE` for what is true of
the run right now, `EPISODIC_MEMORY` for what its finished runs recorded.
Each carries the `domains` a query of that scope may range over (a
`QueryDomain(name, entity_type, objects)` per variable), any `extra_names` its
questions need in scope, and the `evaluation` that works the answer out:
`InMemoryEvaluation` by default, or `DatabaseEvaluation` to translate the query
into SQL (`krrood.ormatic.eql_interface.eql_to_sql`) and run it where the
results live. A domain answered from a database names no `objects`.

The bridge then serves four more endpoints:

```
GET  /presets     {ok, title, presets: [{text, code, scope}],
                   scopes: [{name, label, variables}], variables: [name]}
GET  /vocabulary?scope=      {ok, entries: [{name, kind, detail, module, type}]}
GET  /members?name=&scope=   {ok, name, members: [{name, kind, detail}]}
POST /eql         {code, scope} -> the rendered answer rows
```

The panel groups the buttons under each scope's heading and posts the scope its
button belongs to; a question typed from scratch asks `current_state`.

The EQL panel routes to them automatically while it is attached (see
`web/core/query_source.js`), and falls back to `/api/*` against the recorded
scene when it is not. Queries are serialized behind a lock, because krrood's
`SymbolGraph` singleton is not threadsafe.

Two rules a source has to keep:

- **Never read the world from `knowledge()`.** It runs on an HTTP thread; only
  the simulation thread may touch the world (see `cramera/live/hooks.py`).
  Project what you want queried into plain dataclasses on the demo's own
  thread, and let the domains range over those.
- **Read the lists fresh on every call**, so an answer describes the demo as
  it stands now rather than when the bridge was wired up.

A scene bundle may also ship a `presets.json`
(`{"presets": [{"text", "code", "scope"}]}`)
declaring the questions worth asking about the demo it was recorded from.
Those replace the generated scene presets for that scene, and the panel shows
them greyed out until a demo is attached to answer them.
`experiments/src/experiments/montessori/live_query_source.py` is a worked
example of both halves.

Answers arrive with the question read back as English, coloured by semantic
role (`cramera/knowledge/query_verbalization.py`, built on krrood's own
verbalization grammar), so a preset button says what it asked and not only
what came back. A query krrood has no grammar rule for still answers; it just
gets no sentence.

### What a query may name, and completing it as you type

A query is not limited to the ready-made variables: **every class of the
workspace can be named in one**, so `Body`, `World` or a coraplex designator
work as they do in Python. The names come from the architecture scan
(`cramera/knowledge/workspace_classes.py`): a class is nameable when it belongs
to a workspace package, lives in that package's `src/` tree, and is not one of
the ORM classes generated from another class. About 3,000 names qualify.

Nothing is imported until a query actually uses a name:
`WorkspaceClassNamespace` looks it up in the index on first use and imports only
the module that defines it. A name several modules define — `Descriptor` lives
in 36 — resolves to the candidate from the package declared first in
`WorkspacePackage`, and the suggestion menu labels it with the module it
resolved to and how many others were passed over. A name no class has still
fails as the `NameError` it always was.

The query box completes what it can name, like an editor:

- typing filters the menu by what you have typed — a prefix, or a name's
  capitals (`BCC` finds `BodyCollisionCheck`),
- a dot after a variable or a class offers that type's fields, properties and
  methods,
- ArrowUp / ArrowDown pick, Tab or Enter accepts, Escape closes, and with the
  menu closed Enter runs the query as before.

`web/core/completion.js` decides what to offer for the word under the caret and
`web/panels/eql/suggestions.js` shows it. Both halves are fed by whichever
source answers the queries, so an attached demo completes its own variables
while the recorded scene completes the scene's.

### Driving the running demo

A demo can also offer itself to be paused, restarted and looped:

```python
from cramera.live.bridge import BRIDGE
BRIDGE.register_run_control(MyDemoRunControl(...))
```

A run control implements `cramera.live.run_control.LiveRunControl`: a
`title()`, the `state()` it is in, and `apply(command)` for each
`RunCommand` (`pause`, `resume`, `restart`, `enable_loop`, `disable_loop`).
Two more endpoints follow:

```
GET  /run   {ok, title, paused, looping, restart_pending, activity, iteration}
POST /run   {command} -> the run state that command produced
```

The same state rides along on `GET /info`, so the viewer's existing 3 s poll
is what keeps the controls current; the scene panel turns it into buttons
through `web/core/run_control.js`. Commands are serialized behind their own
lock, so two viewers clicking at once cannot interleave inside the demo's
flags.

What a command *means* is the demo's to decide, and the two halves differ in
when they take effect: pausing can be immediate (freeze the physics where it
stands), while abandoning a run generally cannot — a plan is mid-motion, so a
restart is best recorded and honoured at the next point the demo can stop
without leaving something half-executed.

### Performing a queried action

An answer row can name an action rather than a state, and such a row is offered
with a **perform** button that has the running demo carry it out. An entity the
demo answers with declares itself performable by returning a
`cramera.knowledge.performable_action.PerformableAction` from a
`performable_action()` method; the query runner then carries one beside every
row, the way it carries a replay window beside a row naming a moment.

What actually performs them is registered like a run control:

```python
from cramera.live.bridge import BRIDGE
BRIDGE.register_action_execution(MyDemoActionExecution(...))
```

An action execution implements `cramera.live.action_execution.LiveActionExecution`:
a `title()`, the `state()` it is in (which action is being carried out, which are
still waiting), and `perform(name)` for the name a pressed button sends. Two more
endpoints follow:

```
GET  /perform  {ok, title, performing, requested}
POST /perform  {action} -> the state asking for that action produced
```

That state rides along on `GET /info` too, so the same 3 s poll keeps every
button current; `web/core/perform.js` turns it into what each button says.

A robot is generally mid-motion when a button is pressed, so `perform(name)` is
expected to queue the action and let the demo start it at the next point it can,
exactly as a restart is — the waiting count in the published state is what tells
the viewer it was taken.

## Panels — how the UI is composed

The frontend (`src/cramera/web/`) is a set of **panels** mounted into layout
slots. Which panel appears where is decided by **one file**:

```js
// web/config.js
window.CRAMERA_CONFIG = {
  layout: {
    left:  ['robot-scene'],
    right: ['eql', 'graph'],
  },
};
```

Removing a visualization = deleting its id here. Adding your own:

1. create `web/panels/<name>/panel.js`:

   ```js
   Panels.define('my-panel', function (root, bus) {
     root.innerHTML = '<div class="panel-head"><h2>My panel</h2></div>…';
     bus.on('entity:highlight', function (p) { /* react */ });
     bus.emit('entity:select', { id: 'x', detail: {…}, relations: [] });
   });
   ```

2. include the script in `web/index.html`,
3. add the id to `config.js`.

Panels **never call each other directly** — they publish/subscribe on the
event bus (`web/core/bus.js`), so any subset of panels works. The contract
between the built-in panels:

| event                | payload                          | emitted by → consumed by       |
| -------------------- | -------------------------------- | ------------------------------ |
| `scene:part-clicked` | `{id}`                           | robot-scene → eql              |
| `scene:step`         | `{step}` (`'__done__'` at end)   | robot-scene → eql, graph       |
| `live:changed`       | `{on, url}`                      | robot-scene → graph            |
| `entity:highlight`   | `{ids, focus?}`                  | eql → robot-scene, graph       |
| `entity:select`      | `{id, detail, relations}`        | graph → eql                    |
| `kb:ready`           | `{payload}`                      | eql → anyone                   |

### Built-in panels

| panel         | shows                                                        |
| ------------- | ------------------------------------------------------------ |
| `robot-scene` | three.js scene: environment, robot, draggable objects, playback + live controls |
| `eql`         | EQL query console + entity answer panel                      |
| `graph`       | four tabs: Knowledge / Kinematics / Plan / Statechart        |

On the Plan and Statechart tabs the node border is its execution status —
running (amber), succeeded/done (green), failed (red), paused (blue),
interrupted (orange), not started (dim, dashed) — streamed live from the
bridge while attached.

Two things to know about those statuses: coraplex performs only the plan
**root** (`Plan.perform` → `root.perform`), while `ActionNode.notify` merely
expands its children into one merged motion statechart. So a *recorded* plan
tree has real status on the root only. Live, the bridge derives per-step
status from the statechart life cycle via `GiskardExecutable.motion_mappings`
(`{MotionNode: Task}`) and propagates it up the tree; those nodes are flagged
`derived`. Statecharts exist only during execution, so the Statechart tab is
live-only.

## Layout

```
src/cramera/
  server.py        static frontend + JSON API (/api/knowledge, /api/eql, /scenes/)
  paths.py         all filesystem locations (env-overridable)
  knowledge/       the recorded scene as an EQL knowledge base
    knowledge_base.py  the entity lists one scene bundle yields
    eql_session.py     evaluating one EQL query string
    graph_payload.py   the knowledge graph the UI draws
    presets.py         the ready-made queries the panel offers
    views/             the graph-panel tabs and their drill-downs
  live/            stream a running coraplex demo into the viewer
    bridge.py      bridge state + serializers (runs on the sim thread)
    hooks.py       Executor/Plan/GiskardExecutable/mesh hooks
    http.py        the bridge's HTTP endpoints (port 8765)
    __main__.py    cramera-live entry point
  onboard/         turn a demo run into a scene bundle
    demo.py        demo -> scene bundle (record + bundle, one command)
    bundle_urdf.py standalone URDF/xacro asset bundler
  web/
    index.html     shell: topbar + slots + script includes
    config.js      which panels are shown where  ← edit this to swap panels
    core/          bus, panel registry, split/resize helper
    panels/        robot_scene/, eql/, graph/
    vendor/        three.js, vis-network, … (all local, no CDN)
```

## Tests

```bash
pytest test/cramera_test
```

The JS core (bus, registry, graph status rendering) is covered by node-based
tests invoked from pytest (skipped when node is unavailable).

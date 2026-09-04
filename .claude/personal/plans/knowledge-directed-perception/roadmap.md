# Knowledge-directed Montessori perception

The claim this plan exists to support: a robot that knows what it is looking
at, what supports it, what it just did to it and what it is about to do
perceives better than one that does not — and the cognitive architecture is
what makes that knowledge reach perception at all.

The demo is the Montessori shape-sorting board on Tracy's brushed steel table.
Per-round implementation detail for the branch this work grows out of stays in
`.claude/personal/pr-progress/tracy_icra.md`, which keeps working independently
of this plan; what follows is the reasoning, not the log.

## Where this starts: three faults that are one fault

Observed on the running node on 2026-08-28.

1. **The workspace clip shows the floor.** `WorkspaceBox.clip` works — the
   blacked-out strip in the colour window is it. But `TRACY_WORKSPACE`
   (`node.py:102`) is a hand-written `x 0.35–1.35, y −0.45–0.75`: a 1.0 × 1.2 m
   guess that reaches past the table onto the floor, the chairs and the bottles
   at the far edge. Meanwhile `table_top_z()` already pulls the tabletop's
   collision shape out of the fetched world to read its height, and discards
   `scale.x`, `scale.y` and the origin — which are exactly the bounds being
   guessed at.

2. **A piece resting on the board's lid is never found**, for two independent
   reasons. `MontessoriPerceptionPipeline.detect` rectifies loose pieces onto
   exactly one plane, `table_height`, so a piece standing ~80 mm higher is
   parallax-displaced by centimetres in both the base and top views and never
   survives their intersection. And `pipeline.py:626` reads
   `if board is not None and board.encloses(x, y): continue` — the board is
   coded as an obstacle to exclude, when physically it is a supporting surface
   exactly like the table.

3. **Duplicate detections ride the board's borders**, most often as triangular
   prisms. A lid border is a long, straight, sharp edge, and the edge fit lands
   a prism template on it at roughly 0.7 agreement — above the 0.62 threshold.
   `board.encloses` only rejects a contour whose *centre* falls inside the
   board outline, and a contour on the border has its centre outside it. There
   is also nothing anywhere forbidding two detections from occupying one place.

All three are the same fault: the scene is described to perception by constants
instead of read from the world the node already fetches. That is why wave 1
fixes them by removing the constants rather than by patching each symptom —
patching would mean writing those constants a second time before deleting them.

## Why not build this inside RoboKudo

Decided 2026-08-28 with the developer. **Own reasoning layer, detectors behind
an interface, a RoboKudo analysis engine as one of those detectors later.**

RoboKudo is real and works here — it imports, it has 46 annotators, ~30 analysis
engines, a `SemanticDigitalTwinConnector`. What it does not have is the thing
this plan is about:

- Its knowledge coupling is **one-way**. `SemanticDigitalTwinConnector` pushes
  hypotheses *into* the digital twin. Nothing in the tree reads the world to
  decide what the tree should do. That direction would be new work there, not
  an extension of something existing.
- Its request interface is `robokudo_msgs/Query` → a flat `ObjectDesignator` of
  type/shape/colour/location strings over a ROS action. Replacing that with the
  entity query language is not extending RoboKudo, it is replacing its front
  door.
- Pipeline choice is "pick an analysis engine file". A behaviour tree's
  structure is fixed when it is built; this plan wants it chosen per request
  from the current world state.

Against that, our side already has the data structures (dataclasses, under
test, typed against the digital twin) and, decisively, `krrood`'s `Query` is an
inspectable expression tree with an extensible backend protocol — so the whole
idea rests on machinery that exists.

RoboKudo is kept, though, and not written off: a knowledge layer that can
choose *between* a model-based fit and a learned detector is a much stronger
claim than one that only ever calls our own code, and it makes "move this into
RoboKudo after the deadline" an adapter rather than a rewrite. That is item
`robokudo-detector`, deliberately last and deliberately droppable.

## Why perception is a backend, not a parser

Revised 2026-08-28, at the developer's suggestion, before the manifest was
first saved. The original shape had perception *parse* an incoming query, which
the developer rightly called ad hoc rather than native.

`krrood.entity_query_language.backends.QueryBackend` is an established ABC with
two families (`SelectiveBackend`, `GenerativeBackend`) and four implementations,
and `Query.evaluate(backend=…)` already takes one. `SQLAlchemyBackend` settles
the question:

```python
def _evaluate(self, expression: Query) -> Iterable:
    session = self.session_maker()
    translator = eql_to_sql(expression, session)
    yield from translator.evaluate()
```

That is already "translate the query into another engine's plan and execute it
there". A perception backend is the same move against a camera. So the two
options the developer named are not alternatives: **the backend is the native
front door and the query-to-pipeline compiler is what sits behind it**. The
compiler work does not disappear; it gains a contract and stops being a side
door.

Two deliberate departures from the first sketch:

- **Conditions are split, never ignored.** A backend that drops a condition
  with a warning returns wrong answers. Conditions that can be *pushed down*
  shape the search; conditions that cannot are kept as a **residual filter**
  over the detections that come back. Only a condition that can be neither
  raises. This is exactly a query planner's pushdown-and-residual split, it
  makes the semantics exact rather than best-effort, and it reads better in the
  paper than "perception parses the query".
- **The backend declares how it reads.** `QueryBackend.opening_directive` is
  how a backend tells the verbalization layer its verb (`FIND` for selecting,
  `GENERATE` for generating). Perception wants *"Look for …"* — one `Directive`
  member in `krrood`, and the demo can then verbalize the difference between
  recalling something and going to look at it, which is the paper's own
  distinction.

`PerceivedObjects` — the domain that runs the whole pipeline on iteration and
yields everything — is retired by this: a query then runs only what it asked
for.

Open design question, left for the item: whether `PerceptionBackend` subclasses
`SelectiveBackend` (it selects what is really there rather than inventing it,
so probably yes) or warrants a family of its own, given that "existing data"
becomes "the scene".

## What each framework gains

Nothing here is a fork or a workaround; each piece is an extension of the
framework that owns the concept.

- **semantic_digital_twin** — a surface finish annotation (matte / glossy /
  mirror). Colour is modelled, finish is not, and finish is what decides
  whether colour segmentation works at all: the brushed steel table throws a
  diffuse, piece-coloured reflection with no sharp boundary anywhere, which is
  the whole reason the edge fit had to be written. This turns "the steel table
  and the wooden lid need different pipelines" into something the robot knows
  rather than a branch somebody wrote.
- **krrood / entity query language** — a perception backend, and one
  `Directive` member so it verbalizes as looking.
- **Segmind** — nothing new is expected to be needed. `SupportEvent`,
  `LossOfSupportEvent`, `PickUpEvent`, `PlacingEvent` and `InsertionEvent`
  already exist and are already computed over `is_supported_by`. If a detector
  is missing, that is a finding for the item, not an assumption of the plan.
- **RoboKudo** — one adapter implementing the detector interface, no changes to
  RoboKudo itself.

## The three waves

**Grounding** removes the constants: the workspace and every plane height come
from the world; every supporting surface gets a detection pass at its own
height; a detection may not sit inside a body already known, nor on top of
another detection. Its three items are the three faults above.

**Requests** makes asking and looking the same act: the perception backend with
its pushdown/residual split, the surface-finish annotation, and the rule tree
that reads both to choose a detector. `choose-detection-method` is the item the
paper's central claim rests on — it is where perception measurably improves as
the robot knows more.

**Expectation** closes the loop. Segmind's support events and an action's own
declared effects arm what perception expects: after `LossOfSupport(piece,
table)` stop searching the table; after `Placing(piece, lid)` search the lid.
The action model gets there first, since an action declares its effect before
the event confirms it. The same mechanism is free failure detection —
perception looked exactly where the action promised, found nothing, and says
so, which is what a recovery can act on.

## The deliverable is the demo, not the pull requests

Added 2026-08-28 after the developer pointed out that the first cut of this
plan tracked nine engineering items and none of them meant "the demo runs".
That was a real gap: the deadline is a working demonstration on `tracy_icra`,
and a plan that only tracked branches off `main` could have every item green
while the robot ran none of it.

**The standing rule: an item's branch merges into `tracy_icra` as soon as it
works, without waiting for its own pull request to land on `main`.** The pull
request is the review record; `tracy_icra` is the running truth. Coupling them
would let review latency starve the demo, which is the one thing that cannot
slip. When review changes an item afterwards, re-merge.

**Each wave has a demo item** saying what has to be true on the real robot
before the wave counts as finished — `demo-runs-on-grounded-perception`,
`demo-asks-by-query`, `demo-detects-and-recovers-a-failed-insert`. They sit in
their own tracks so they run alongside the engineering rather than queueing
behind it.

**`demo-catches-up-with-main` comes first, and should be done immediately.**
Measured 2026-08-28: `main` is 234 commits ahead of `tracy_icra`, their merge
base is `1646dd355` from 2026-08-19, and a trial merge (`git merge-tree
--write-tree`) conflicts in exactly one file —
`semantic_digital_twin/src/semantic_digital_twin/adapters/multi_sim.py`, a
colleague's Mujoco work, unrelated to perception. Every later item in this plan
is developed off `main` and has to reach this branch, and this merge only gets
more expensive while it waits.

**If the deadline forces a cut**, protect
`demo-detects-and-recovers-a-failed-insert` — it is the end-to-end story the
paper is written around — and drop `robokudo-detector`, which nothing else
depends on and no demo item needs.

## The budget: 2026-09-15

Thirteen working days from 2026-08-28 (Fri 28th, then two full weeks, then the
14th and 15th). **That is less than the full scope needs, and pretending
otherwise would be the most expensive mistake this plan could make.** If the
paper is written in the same window, code has to stop around the 8th or 9th,
which halves it again.

**The cut comes from depth, not from pillars.** Every item here is load-bearing
for the claim — knowledge reaching perception is the whole argument, so dropping
the events, the rule tree or the backend does not shorten the paper, it removes
it. What shortens is building each one in the narrowest form that demonstrates
its claim:

- `perception-backend` — support exactly the condition forms the demo writes
  (the selected type, `is_supported_by`); push those down, keep the rest as
  residual filters, raise on anything else. A general query compiler is not
  what the claim needs.
- `choose-detection-method` — two rules *is* the demonstration: the steel table
  choosing the edge fit, the board's lid choosing the colour blob. The tree's
  generality is what makes a third rule cheap; it does not need proving up
  front.
- `expectations-from-events` — report the violated expectation. Let recovery be
  the plan re-asking, not a policy of its own.

`robokudo-detector` is `deferred` outright, past the deadline.

**Two things bought schedule rather than costing it:**

- `expectations-from-events` was re-pointed from `choose-detection-method` to
  `perception-backend`. Arming an expectation is a search-space constraint —
  "look at the lid, not the table" — which is the backend's pushdown; choosing
  *how* to look is independent of it. So wave 3 and the method-selection track
  now run in parallel instead of in series, which is where the schedule was
  tightest.
- `depends_on` in this plan means **stacked on**, never **waiting for a merge**.
  Every item of `montessori-eql-stack` is based on an unmerged parent and this
  works the same way, so `montessori-perception-on-main` costs the demo nothing
  and can land whenever review allows — after the deadline included.

**Suggested order, with the first demonstrable state early:**

| when | what | state reached |
|---|---|---|
| 28 Aug | `demo-catches-up-with-main`, `montessori-perception-on-main` | mechanical, both cheap today |
| 31 Aug – 2 Sep | wave 1's three items; `surface-finish-annotation` alongside | |
| 3 Sep | `demo-runs-on-grounded-perception` | **the demo looks right on the real robot** |
| 4 – 8 Sep | `perception-backend`, then `choose-detection-method` and `expectations-from-events` in parallel | |
| 9 Sep | `demo-asks-by-query` | **the central claim is demonstrable** |
| 10 – 11 Sep | `demo-detects-and-recovers-a-failed-insert` | **the end-to-end story runs** |
| 12 – 15 Sep | results, figures, writing, and the slack every one of the above will need | |

Getting to a demonstrable state on the 3rd matters more than the order looks:
from there on, every later item improves a demo that already runs, so a day
lost late costs a feature rather than the deliverable.

## Sequencing decisions

- **The perception package lands on `main` first** (`montessori-perception-on-main`).
  `experiments/src/experiments/montessori/perception/` exists on no branch but
  `tracy_icra`, which also carries seventeen unrelated commits (Franka demos,
  Mujoco tuning, stacking work). Every item in this plan edits those files, so
  without this they would all stack on a branch whose upstream points at a
  colleague's fork and which cannot reasonably be proposed as a whole. The
  landing branch carries the perception package alone — sorinar329's original
  node commit `75258debd` plus the seven that follow it. `tracy_icra` itself is
  left alone.
- **The `surfaces` track is sequential.** Its three items edit the same
  pipeline in turn, so they stack rather than run in parallel; splitting them
  would mean two branches independently rewriting the same file.
- **`surface-finish-annotation` depends on nothing** and can start immediately
  off `main`: it touches only `semantic_digital_twin`.
- **`robokudo-detector` is last and droppable.** Nothing depends on it, and if
  the deadline tightens, items 1–8 stand without it.

## Relationship to `montessori-eql-stack`

Different initiative, same demo. That plan is about *asking* — the console, the
autocomplete, the spoken questions, the replay. This one is about *answering by
looking*. They share no code, but they meet at the backend: once perception is
a query backend, a question typed into that console can be answered by the
robot going and looking, rather than only by reading what it already recorded.
Worth revisiting once `perception-backend` lands.

## `demo-catches-up-with-main`: the merge, and the one conflict

Run 2026-08-28. Measured at the time of the merge rather than when the plan
was written: `main` was **277** commits ahead of `tracy_icra` (the plan's
earlier figure of 234 was four days stale), `tracy_icra` 28 ahead of `main`,
merge base `1646dd355` from 2026-08-19. The conflict was where the plan
predicted, in exactly one file —
`semantic_digital_twin/src/semantic_digital_twin/adapters/multi_sim.py` — but
it was **not** the trivial one the plan expected. Eight hunks, and both sides
had genuinely reworked the same MuJoCo sync methods:

- `main` had extracted `_read_connections_from_qpos` and
  `_write_connections_to_qpos` out of `_sim_to_world`/`_on_state_change`, and
  put the whole pull under `World._world_lock` — with a recorded rationale
  about a writer thread landing mid-pull and having its write silently lost.
- `tracy_icra` had, independently, wrapped those same loops inline in
  `_model_lock` plus `renderer.lock()`, and added the
  `physically_simulated_dofs` behaviour: a qvel readback so a stall detector
  sees real physical settling, and a `ctrl`-setpoint path
  (`_integrate_desired_position`) so a controller pushing against a contact
  builds up servo force instead of chasing the measured stall position.

**Resolved as a union, taking `main`'s structure.** `main`'s extraction
subsumes the inline `_model_lock` loops, so `_sim_to_world` and
`_on_state_change` are `main`'s. What `main`'s helpers did *not* have is
`renderer.lock()`, which guards against a non-headless viewer's own native
rendering thread; that is carried into both helpers, with the reason recorded
there. Every `physically_simulated_dofs` behaviour is kept in full, renamed
onto `main`'s `qpos_address` parameter (`main` had spelled out `qpos_adr` in
the same round). `njmax` and `_thickened_mesh_paths` in `_start_build` were
independent additions from either side; both kept.

Relative to `main`'s copy of the file the resolution adds 272 lines and drops
14, and each of those 14 is accounted for: the two `_model_lock`-only `with`
statements that gained `renderer.lock()`, and the two lines of the thin
`_write_1dof_to_qpos` that the `physically_simulated_dofs` version replaces.

**The merge also drops the tracked `ormatic_interface.py` files this branch
still carried.** `main` had already untracked them, which `AGENTS.md` requires
— they are generated, and a tracked copy is what used to make branch switches
fail. Taking `main`'s side here is the point of the merge, not a side effect
of it.

**The conflict was not the whole merge.** Three call sites in files that exist
only on this branch were left calling code `main` had removed or moved. None of
them conflicted, because `main` never had those files to change — which is
exactly why a clean `git merge` is not evidence a branch this old still runs:

- `pickup_demo_real.py` called `VizMarkerPublisher.with_tf_publisher()`, removed
  on `main`; the publisher now builds its own `TFPublisher` in `__post_init__`.
- `insert_shape_action.py` imported `translate_free_space_to_where_condition`
  and `navigation_map_at_target`, both moved onto `PlanarGraphOfBoundingBoxes`.
  `main` migrated `sage10k_actions.py` the same way in the commit that moved
  them, so that migration is the exemplar this one follows.
- The same file passed a `Point3` to a planar graph's `node_of_point`, which
  binds `Point2` — the stale query-point call site that commit `1a6d4206` fixed
  in `sage10k_actions.py` and could not fix here.

They were found by resolving every name the branch's own files import against
the merged tree, not by reading the diff. Worth repeating on the next merge:
the textual conflict is the part `git` can see, and it was the smaller half.


**What could and could not be verified, and why.** The repository's own test
suite does not run in a Claude Code container: `semantic_digital_twin`'s
conftest regenerates the ORM interfaces on collection, that generation imports
`giskardpy`, and `giskardpy` needs a ROS 2 installation that is not there. It
fails identically on unmodified `origin/main` in the same container, so this is
the environment and not the merge — but it does mean *no* test ran. What was
done instead: the whole tree byte-compiles under Python 3.12 (the version the
sources need, for `type X[T] = ...`); every name every file the branch touches
imports from workspace source resolves against the merged tree, which is what
found the three broken call sites; and each of the 14 lines the resolution drops
relative to `main`'s copy of `multi_sim.py` is individually accounted for.

That is real verification, and it is still not a test run. The `multi_sim.py`
sync path in particular is threading code whose failure mode is a write lost
under contention, which no unit test in that module exercises anyway. The merge
is proven by the demo running on the real robot — which is
`demo-runs-on-grounded-perception`'s job, and one more reason to get there by
3 September.

## `montessori-perception-on-main`: what the package actually needed

Run 2026-08-28, as pull request #202 off `main`. Twelve commits, 34 files,
9,664 insertions, zero deletions.

**The item's premise was wrong in one respect, and it matters for the items
stacked on it.** The plan described this branch as carrying "the perception
package alone — sorinar329's original node commit `75258debd` plus the seven
that follow it". Those eight commits are exactly right and all eight are here,
with sorinar329's authorship preserved on the first. But the package does not
import-close against `main`: four files it reads exist only on `tracy_icra`.

| file | lines | what it is here for |
|---|---|---|
| `montessori/semantics.py` | 345 | `MontessoriShapeCategory`, the shape vocabulary everything is typed against |
| `montessori/hole_geometry.py` | 237 | the board's hole footprints, read by the test renderer and by `world.py` |
| `montessori/world.py` | 1167 | `BOARD_SCALE`, and nothing else |
| `tracy_experiments/equipment.py` | 579 | `table_top_z`, and nothing else |

The last two contribute a single symbol each. **Both symbols are exactly what
`surfaces-from-world` replaces with values read from the world**, so this
coupling is expected to be short-lived — which is worth knowing when that item
runs, because deleting those two dependencies is a visible, checkable outcome
of it rather than an incidental cleanup. Their own tests came across too, so
`main` gains no untested code.

The eight commits' hunks touching `montessori_demo.py` and
`tracy_experiments/montessori/world.py` were dropped: those files stay on
`tracy_icra`.

### Two gaps that only appear off `tracy_icra`

Both are environment accidents on the demo branch, and both would have broken
a fresh checkout of `main`:

- `hole_geometry.py` loads `resources/board.stl` **at import time**, and the
  mesh is not a Python file — so an import-closure check over modules alone
  never sees it. Without it, importing `experiments.montessori.world` raises
  before any test runs.
- `experiments` has never declared `opencv`, though the perception package
  imports `cv2` in six modules. It works on `tracy_icra` only because
  `robokudo` pulls opencv into the same environment.

Worth generalizing: a closure check that only follows `import` statements
proves less than it looks. Data files loaded at import time and undeclared
third-party packages both sit outside it.

### Verification

140 passed, 1 skipped — every test the branch adds, run against the branch.
Run with `--noconftest` and the workspace on `PYTHONPATH`, because the
repository's conftest regenerates the ORM interfaces on collection, which
imports `giskardpy` and needs a ROS 2 installation the container lacks; that
failure reproduces on unmodified `main`, so it is the environment, not the
branch. The ORM path is therefore unexercised here.

### Opened ready for review, deliberately

The dashboard's `is_ready_to_unblock_dependents()` counts a dependency as ready
only when it is done, merged, or **open and out of draft** — a still-open draft
is the one state it refuses to let a dependent stack on. So a draft pull request
here would have left `surfaces-from-world` and `perception-backend` showing as
blocked with no "Start now" button, which is what prompted this item being
picked up. Opened out of draft at the developer's decision, to unblock them.
Nothing is merged; `main` is untouched until they say otherwise.

## `surfaces-from-world`: the plan, and what it deliberately leaves to the next item

Kicked off 2026-08-28 in `auto` mode, as pull request #205 off
`montessori_perception_on_main` (#202, open and out of draft, so ready to stack
on — `check_dependency_readiness.py` reports `open_ready`).

### The two constants, and where each one is

`node.py` reads the scene from exactly two hand-written values:

- `TRACY_WORKSPACE` (`node.py:102`), the 1.0 × 1.2 m region guess. This is
  fault 1 in full.
- `float(BOARD_SCALE.z)`, `build_node`'s default lid offset, imported from
  `experiments.montessori.world` — the *simulated* scene's own module constant,
  standing in for the real board's height.

`table_top_z(robot)` is not a constant, but it throws away three quarters of
what it reads: it picks the tabletop out of `robot.root.collision` by largest
`scale.x * scale.y`, keeps the height, and discards `scale.x`, `scale.y` and
the origin — the exact numbers `TRACY_WORKSPACE` guesses at.

So the same read that already gives the height gives the bounds, and the fix is
to keep what it discards rather than to write a better rectangle.

### What is being built

One place that answers "which horizontal surface is this, where does it reach,
and how high does it stand", returning both together rather than a bare float:

- Prefer `HasSupportingSurface.supporting_surface` when the world carries one.
- Fall back to the body's own tabletop collision shape — `table_top_z`'s
  existing largest-area pick, now keeping the extent as well as the height.

`build_node` then reads the table and the board's lid out of the fetched world
and hands the pipeline a region and two plane heights that came from the world.

**`supporting_surface` is `None` on every world in this workspace today.**
Nothing calls `calculate_supporting_surface`, and the field defaults to `None`,
so on the live robot the fallback is the path that actually runs. The annotated
path is written because the item asks for it and because
`detect-per-supporting-surface` will populate it, not because it fires now —
worth knowing before reading the fallback as dead code.

### Deliberately not done here

- **The pipeline keeps `region` / `table_height` / `board_height` as they are.**
  Restructuring it into one pass per surface is `detect-per-supporting-surface`,
  the next item in this track, and building it here would take that item's work.
  The lid offset is computed at the wiring site from two world-read heights
  instead.
- **The region is the table, not a reachability envelope.** `TRACY_WORKSPACE`'s
  docstring calls it "the reachable stretch of Tracy's own table", but nothing
  in this plan asks perception to clip to what the arms can reach, and fault 1
  is the region showing the *floor*, not showing unreachable table. If the real
  table turns out wider than the arms reach, that is a new observation and a new
  item, not a constant to reintroduce.

### The checkable outcome

`montessori-perception-on-main`'s own roadmap section recorded that
`montessori/world.py` and `tracy_experiments/equipment.py` were dragged onto
`main` for a single symbol each — `BOARD_SCALE` and `table_top_z` — and that
"both symbols are exactly what `surfaces-from-world` replaces with values read
from the world". So the test of this item is not only that the clip looks right:
it is that `node.py` imports neither module afterwards. That is asserted, not
just observed.

### Verification

Tests first, against `MontessoriWorld` — a synthetic world already carrying a
`Table`, a `Floor` and a `ShapeSortingBoard`, which `test_montessori_world.py`
builds today — so the derived region and heights are asserted against the
world's own `TABLE_SCALE`/`TABLE_POSITION` and `BOARD_SCALE`/`BOARD_POSITION`
rather than against a second copy of those numbers.

Run with `--noconftest` and the workspace on `PYTHONPATH`, for the reason #202
recorded: the repository's conftest regenerates the ORM interfaces on
collection, which imports `giskardpy` and needs a ROS 2 installation the
container lacks, and that failure reproduces on unmodified `main`.

Nothing here can be verified against the live camera from a container. The clip
actually showing the table is `demo-runs-on-grounded-perception`'s job.

### What it actually took, and two things the plan did not know

Built 2026-08-28 as pull request #205, `d8f30ffb`. 9 new tests; `137 passed, 1
skipped` across the four `test_montessori_*` modules against `128 passed, 1
skipped` on the parent branch.

**The `world.py` coupling is not fully gone, and the plan implied it would be.**
`pipeline.py` reads `BOARD_SCALE` too, for `BoardDetector.board_footprint` — how
far apart two holes may lie and still belong to one board. That is a detector
tolerance rather than a plane height or the workspace, so it is not what this
item removes, and rewriting it would take `detect-per-supporting-surface`'s
ground. The checkable outcome therefore narrowed to what is actually true:
`node.py` imports neither module, asserted directly by
`test_the_node_takes_no_scene_constant_from_another_module`. The `equipment.py`
coupling *is* gone outright.

**Widest face or highest face — left as the developer's call.** `of_body` picks
the body's widest horizontal face, which is exactly the pick `table_top_z`
already made for the height alone. The obvious alternative, the *highest* face,
is arguably the truer reading of "the surface things rest on", and a test
written against a wide-based pedestal caught the two rules disagreeing. They
diverge only for a body whose widest shape is not its top: a splayed base, or a
mounting plate sitting on the tabletop as part of the same body — and that
second case is a plausible reason `table_top_z` chose widest against the real
URDF in the first place. Overturning a choice made against hardware that cannot
be inspected from a container is not this item's call to make silently, so the
existing rule was preserved and the question raised on the pull request instead.

**A world with no board is refused rather than assumed.** Once the constant is
gone the lid's height cannot be invented, so `MontessoriPerceptionPipeline.of_world`
raises `BoardMissingFromWorld`. This is a real behaviour change for a caller
whose fetched world carries no `ShapeSortingBoard` — but
`detect-per-supporting-surface` needs the board in the world regardless, so the
requirement arrives with this item rather than being deferred into it.

`supporting_surface` was `None` on every world in this workspace as predicted,
so the fallback is the path that runs; the declared-region path is covered by a
test that places a `Region` in its own world.

### `surfaces-from-world`: what was actually stalling it, and where the fix belonged

Resolved 2026-08-29 in `auto` mode. **The item's own branch had nothing wrong with it.**
#205 was green on all 23 checks, `mergeable_state: clean`, its dependency #202 `open_ready`,
and two of its three review threads already answered and resolved. What kept it open was the
third: "This is a very big file" on `test_montessori_perception.py`, which the developer
answered at 18:38 with **"ok it should be done on 202"**.

So the work the item was waiting on was not the item's. The mechanical scope check settles
it the same way the developer did: `git ls-tree main -- test/experiments_test/test_montessori_perception.py`
is empty, so the file exists on no branch but `montessori_perception_on_main`, and whichever
pull request introduces a file owns changes to it. Splitting it on #205 would have put
base-branch work in the child.

**Done as `00721be7` on `montessori_perception_on_main`**, merged into #205 by `d6673b48`.
The 1262 lines became six modules, one per subject - camera decoding, the viewer, footprints,
the views (rectification, workspace clip, overlay), piece matching, and the pipeline and its
queries. Every one of the fourteen `# %%` sections moved verbatim and all 77 test functions
were accounted for, both verified mechanically rather than by eye, and the six modules run the
same `91 passed` the one file ran.

**The four fixtures three modules share** - `renderer`, `placed_pieces`, `pipeline`, `scene` -
moved to `test/experiments_test/dataset/montessori_scene_fixtures.py`, beside the renderer they
build on, and are registered with `pytest_plugins = [montessori_scene_fixtures.__name__]`. Not
imported by name, which would put `scene` and `pipeline` in module scope where every test's own
parameter of that name shadows them; and not a `conftest.py`, because the one in
`test/experiments_test/` imports `giskardpy`, so the local runs use `--noconftest` and would
never load it. That constraint is worth remembering: in this container a `conftest.py` is not
available to hold anything shared.

**#202 was left out of draft**, against the standing convention of re-drafting after every push.
Its own section above records that it was opened ready deliberately, because
`is_ready_to_unblock_dependents()` refuses to let a dependent stack on an open draft - so
re-drafting it would have shown `surfaces-from-world` and `perception-backend` as blocked, which
is the exact state that decision exists to avoid. The specific recorded decision about this pull
request wins over the general rule; one click reverses it either way.

**Still open, and not this session's to settle:** whether `WorkspaceSurface.of_body` should pick
the widest horizontal face or the highest one. Raised on #205 at review time and unanswered. The
two rules disagree only for a body whose widest shape is not its top, and the existing rule was
chosen against a real URDF that cannot be inspected from a container.

**Worth repeating:** the item's recorded `blockers` were empty while it sat waiting, and the
cause was a single review comment nobody had turned into state. What the resolve did before
touching any code was write that down.

## `surface-finish-annotation`: where finish belongs, and what it deliberately does not reach

Kicked off 2026-08-29 in `auto` mode, as pull request #216 off `main`. `depends_on` is
empty and `check_dependency_readiness.py` returns `[]`, so nothing was waited on. The
mechanical scope check (`check_scope_overlap.py`, base `origin/main`, against both
in-flight branches) reports `paths_absent_from_base: []` and no shared path with either
`montessori_perception_on_main` or `perception_surfaces_from_world` — those two live
entirely in `experiments/`, this lives entirely in `semantic_digital_twin/`. Genuinely
separate work, exactly as the sequencing section predicted.

### The property goes where colour already is

The item's own premise settles the placement: "the digital twin models a surface's colour
but not its finish". Colour is `Shape.color`, and `Shape.texture` is already an *optional*
appearance property sitting beside it — so finish is the third field on `Shape`, in
`world_description/geometry.py`, and `Texture` is the precedent to copy in every respect
(optional, documented on the field, round-tripped, tested by serialization).

This also happens to be the placement the consumer can actually read. `Body.visual` /
`Body.collision` and `Region.area` are all `ShapeCollection`s of `Shape`, so both routes
`WorkspaceSurface` takes in `surfaces-from-world` — the declared `supporting_surface`
region, and the fallback pick of the body's widest horizontal collision shape — end at a
`Shape`. The fallback is the path that actually runs today, and it is the one where the
finish is read off the very shape whose scale and origin that item already reads.

### `None` is not `MATTE`

`finish` defaults to `None`, meaning *not stated*, rather than to a member. If every
unannotated surface read as matte, `choose-detection-method`'s "a matte contrasting
surface selects the cheaper colour blob" rule would fire on the steel table the moment
someone forgot to annotate it — a silently wrong dispatch rather than a visible gap.
`Optional` is also what `texture` does on the same class for the same reason.

### One read of `Shape`'s own fields, not four

`Sphere`, `Cylinder` and `Box` each re-read `origin`, `color` and `texture` in their own
`_from_json`; `Mesh` re-reads `origin` and `scale`. Adding a fourth field would have
written the same line a fourth time in each. So the fields `Shape` itself declares are
read once, by `Shape.arguments_from_json`, and each primitive's `_from_json` supplies only
its own geometry. The refactor is caused by this change rather than bundled with it: it is
the DRY-compliant way to add the field, and the parametrized round-trip tests over all
three primitives are what hold it.

### `Mesh` carries the finish, but still not the colour or the texture

`Mesh._from_json` goes through `from_trimesh`, which reconstructs the shape from the
exported file and has never restored `color` or `texture`. That is deliberate for both:
a mesh's colour lives in its vertex colours, and its texture in its trimesh visual — the
field on `Shape` is documented as not applying to meshes. Finish has no such carrier.
Leaving it out would mean a mesh-modelled table — which a real URDF is more likely to give
than a primitive — loses the annotation on every round trip. So `from_trimesh` gains a
`finish` parameter and `Mesh._from_json` passes it through. Colour and texture are left
exactly as they were; fixing those is not this item's claim.

### Deliberately out of scope, both recorded rather than silently skipped

- **No adapter infers a finish.** A MuJoCo material carries `specular`, `shininess` and
  `reflectance`, and the MJCF adapter already reads that material for `Color` and
  `Texture`. Mapping three continuous numbers onto three finishes means choosing
  thresholds, and `AGENTS.md` forbids inventing numbers whose rationale nobody can state.
  The finish is declared by whoever builds the world, which is where Tracy's table is
  described anyway.
- **A derived supporting-surface `Region` does not inherit its body's finish.**
  `calculate_supporting_surface` builds the region from `self.root.combined_mesh` — every
  collision shape at once — so there is no single shape to take a finish from, and a body
  whose shapes disagree would need a merge rule nothing asks for yet. `surfaces-from-world`
  already recorded that `supporting_surface` is `None` on every world in this workspace and
  that nothing calls `calculate_supporting_surface`, so propagating it would be an invented
  rule on a path that does not run. **Worth knowing for `detect-per-supporting-surface`:**
  when it populates `supporting_surface`, the finish has to be declared on the region it
  builds, or read from the body's shapes at that point.

### Verification

Tests first, in `test/semantic_digital_twin_test/test_geometry/test_shape.py`, asserting
against the `SurfaceFinish` member rather than against a string copy of it, and
parametrized across `Box`, `Sphere`, `Cylinder` and `Mesh` so the shared-read refactor is
covered on every shape it touches.

Run with `--noconftest` and the workspace on `PYTHONPATH`, for the reason #202 and #205
both recorded: this repository's conftest regenerates the ORM interfaces on collection,
which imports `giskardpy` and needs a ROS 2 installation the container lacks, and that
failure reproduces on unmodified `main`. `ormatic` maps `Enum` through
`PolymorphicEnumType`, so the generated ORM interface is expected to take the new field
without a source change — whether the regeneration can actually run in this container is
reported with the result rather than assumed.

## `montessori-perception-on-main`: the review round of 2026-08-29, and where it went

Resolved 2026-08-29 in `auto` mode. **Nothing was wrong with the branch.** #202 was green
on all 23 checks, `mergeable_state: clean`, and carries `cram2-link-sent` rather than
`in-review`, so there is no upstream pull request holding review of its own. What kept it
open was thirteen unresolved review threads, of which the item's own `blockers` recorded
none and its `notes` described two — wrongly, at that: the note named "a timedelta on
node.py:134" for what is a hard-coded 0.05 second poll interval at line 374. That is the
second time on this plan that the cause of a stall was a review comment nobody had turned
into state.

**The thirteen are four asks and one ask.** Four are local to this branch and were done
here:

- `NoMatchingHoleError` moved out of `semantics.py` into `experiments/montessori/exceptions.py`,
  beside the perception package's own `exceptions.py` (`bb37390d`). Writing the test for
  the raise found that no test had ever reached it, and that the two existing tests build
  their board with `name=PrefixedName(...)` where the API takes a `str`, which double-wraps
  the name and makes the error's own message raise `TypeError`. The new test passes a plain
  string, as the production code does; the existing tests were left alone, since they never
  format the name.
- `HoleFootprint`'s centre, bounding-box size and boundary points became `PlanarPoint` and
  `PlanarSize` instead of bare pairs (`3348e353`), so no reader has to remember that index
  0 is x. `semantic_digital_twin`'s own `Point2` was considered and not used: it is a
  casadi symbolic point carrying a reference frame, and these are plain metres in the
  board mesh's local frame, several hundred to a hole.
- The perception package's `__init__.py` is empty (`be8b8514`), like every other one under
  `experiments`.
- The node's poll interval is a field with 0.05 as its default (`a9204f5e`), beside the
  `minimum_period` the pipeline runs at. `node.py` imports `rclpy`, which no environment
  in this workspace has, so it has no tests here and this change is covered by nothing but
  the compile.

The other nine are one ask, and the developer placed it himself: *"Check the plan items
for the knowledge guided perception plan, and see where this modification or feature
should be, in a new plan item or in an existing plan item. Because I guess this PR here is
for combatibility with main."* The numbers the detectors carry are knowledge about the
pieces, the surfaces and the lighting, and belong on those objects with a rule tree
concluding them — which is `choose-detection-method`'s mechanism applied to the detector's
parameters rather than to the choice of detector. That is now
**`detector-parameters-from-knowledge`**, and the developer's interactive-presenter
suggestion is **`tune-detection-rules-against-the-camera`**, deferred past the deadline
alongside `robokudo-detector`.

They are new items rather than folded into `choose-detection-method` because substantial
work remains once the overlapping edits are removed: moving the parameters onto the twin's
objects and surfaces stands on its own, and doing it inside the item the paper's claim
rests on would put that item's delivery behind it. The scope check says the same thing
from the other side — every file this touches is introduced by #202 itself, so path
overlap alone would fold the whole plan into one item.

**A schedule risk this round surfaced.** The developer said krrood's ripple-down rules are
not usable yet and expects them to become so through the RDR/EQL refactor's integration
build. `choose-detection-method` is planned for 4–8 September and cannot start before
they are, and `detector-parameters-from-knowledge` now sits behind it. Recorded on both
items rather than only here.

**#202 stays out of draft**, for the reason its own section already records: a dependent
cannot stack on an open draft, and re-drafting it would show `surfaces-from-world` and
`perception-backend` as blocked.

### `surface-finish-annotation`: what it actually took, and the one thing the plan had not looked at

Built 2026-08-29 as pull request #216, `80100bd4`. 20 new tests; `45 passed` in
`test_shape.py` against `25 passed` on the parent.

**Adding the field meant fixing a duplication first.** `Sphere`, `Cylinder` and `Box`
each re-read `origin`, `color` and `texture` in their own `_from_json`, so a fourth field
would have written the same line a fourth time in each — exactly what `AGENTS.md` forbids.
The fields `Shape` itself declares are now read once, by `Shape.arguments_from_json`, and
each primitive supplies only its own geometry. The parametrized round-trip tests over all
three primitives are what hold that refactor.

**`Mesh` needed the finish carried explicitly, and the plan had not checked why.**
`Mesh._from_json` goes through `from_trimesh`, which reconstructs the shape from the
exported file and has never restored `color` or `texture` — deliberately, since a mesh's
colour lives in its vertex colours and its texture in its trimesh visual. A finish has no
such carrier, so leaving it out would have lost the annotation on every round trip for a
mesh-modelled table, which is what a real URDF is more likely to give than a primitive.
`from_trimesh` gained a `finish` parameter; colour and texture were left exactly as they
were, since fixing those is not this item's claim.

**The container could run the tests after all, and the ORM with them.** The two items
before this one recorded that the suite does not run in a Claude Code container. That was
true of *this* container too as it arrived — no `trimesh`, no `pytest`, no compiled
`random_events_lib` — but it was a missing environment rather than an impossible one:
installing the dependency set, building the vendored `random_events` from source
(`pip install --no-deps ./random_events`), and copying `urdf_parser_py` in by hand (its
`setup.py` uses an `install_layout` modern setuptools removed) got the suite running.
Python 3.12 is required, not 3.11: `krrood`'s class-diagram parser calls
`make_dataclass(module=...)`, which is 3.12+.

That matters beyond this item, because it means **the ORM path is exercised here for the
first time in this plan**. `scripts/regenerate_all_orm.py` regenerates
`semantic_digital_twin`'s interface and maps the new field as
`finish: Mapped[Optional[SurfaceFinish]] = mapped_column(PolymorphicEnumType,
nullable=True, ...)`. The script still exits non-zero afterwards, on `giskardpy` —
`CouldNotResolveType: QPControllerConfig` — which reproduces without this branch and is
unrelated to it.

**How the whole-suite comparison was made, and one way it can lie.** The first attempt
compared pass counts across a `git stash` of the source, and read as +92 passes for 20 new
tests. The cause was that `ormatic_interface.py` is generated and *not* stashed: the
baseline run was executing against an interface built from the changed source, mapping a
`SurfaceFinish` its own `geometry.py` no longer had. Regenerating the interface on each
side and diffing the *names* of the failing and erroring tests rather than their counts
gives the real answer: the two lists are byte-identical, 160 lines each. Worth repeating
whenever a generated file sits outside the change being measured.

What still fails or errors in this container needs ROS 2 (`rclpy`, `geometry_msgs`,
`visualization_msgs`) or a fixture `--noconftest` skips, and `polytope` and `pydrake` do
not build here at all.

### `montessori-perception-on-main`: the second review round of 2026-08-29

The developer worked through the thirteen threads himself and resolved eleven, leaving two:
a new one on `hole_geometry.py:185`, and a question on the `_SHAPE_COLORS` thread — *"Is this
file actually used in the tracy_icra demo? if not then I do not care about it for now."*

**It is used, including that constant.** `tracy_experiments/montessori/world.py` on
`tracy_icra` imports twenty-four names from `experiments/montessori/world.py`, `_SHAPE_COLORS`
among them, and uses it to colour the loose shapes and the hole markers; that module is
`TracyMontessoriWorld`, which both `montessori_demo_real.py` and `montessori_demo_mujoco.py`
build their scene from. So the question answered itself into doing the work.

- `33fe5a798` — the shoelace helper's `(area, centroid)` pair becomes `PolygonMeasurement`,
  built by `PolygonMeasurement.of`, following the `of` constructor `EdgeDistances` and
  `WorkspaceSurface` already use. It gets the formula's first direct tests; until now it was
  only ever checked through a detected hole's centre.
- `7363d2c26` — `KnownPiece.color` answers what colour a piece is, from the hue measured off
  the real one at full saturation and brightness, and `_SHAPE_COLORS` asks. The cube and the
  cylinder are cyan and the two prisms amber, as they are on the table, instead of red, blue,
  green and orange. The disk and the sphere keep a colour of their own, since this set has
  neither and there is nothing measured to match.

**Two pieces now share a colour in the twin, deliberately.** Cube and cylinder are both cyan,
the two prisms both amber, because that is what the real set looks like — shape is what tells
them apart on the table, and now in RViz too. Only the hue was ever measured, so the pure form
of it is what the twin draws; that assumption is stated on `KnownPiece.color` rather than left
for a reader to infer.

**147 passed, 1 skipped**, against 142 after the first round.

## `detect-per-supporting-surface`: one pass per surface, and where each surface's extent comes from

Kicked off 2026-08-30 in `auto` mode, as pull request #221 off
`perception_surfaces_from_world` (#205, open and out of draft, so ready to stack on --
`check_dependency_readiness.py` reports `open_ready`). The mechanical scope check reports
every path this touches absent from `main` and shared with both #202 and #205, which the
`montessori-perception-on-main` round already recorded as expected: every file in this plan
is introduced by #202, so path overlap alone would fold the whole plan into one item. What
remains once the overlapping edits are removed is the pipeline's restructure into one pass
per surface, which is substantial and stands on its own, so this is ordinary stacking --
the same call the `surfaces` track's "sequential, each item edits the same pipeline the
previous one left behind" already made.

### Two faults, one restructure

`detect` runs the loose-piece detector exactly once, against the table's plane, and hands
it the board so that `board.encloses(centre)` drops whatever stands on the board. Both
halves of fault 2 are that single pass: a piece on the lid is parallax-shifted out of the
intersection of the two table-plane silhouettes, and would be discarded as the board's own
even if it survived.

So the pipeline runs one pass per supporting surface, each rectified onto that surface's
own plane -- which is what cancels the parallax, since a piece on the lid seen from the lid
lies at its own footprint the way a piece on the table already does.

### Which surface a contour belongs to

The two skips are the same rule read from opposite sides: a contour on the table plane
whose centre falls inside the board belongs to the lid, and a contour on the lid plane
belongs to the lid only if its centre falls inside the board. So each pass carries the part
of its plane it may claim -- the outline bounding the surface itself, and the outlines of
the surfaces standing on it -- rather than carrying "the board" as an obstacle.

**The lid's extent comes from the detection, not from the world, and its height comes from
the world.** The rectification needs the height before anything has been detected, and the
lid's height above the table does not change when the board is slid across it; where the
board *is* does change, and the board detector measures it every frame. `of_world` already
discarded `WorkspaceSurface.of(board).region` and kept only its height, so this is the
existing split made explicit rather than a new one.

### The pipeline holds surfaces, not three bare numbers

`region`, `table_height` and `board_height` become the two surfaces themselves, which is
the restructure #205 deliberately left here ("the pipeline keeps `region` / `table_height` /
`board_height` as they are ... building it here would take that item's work"). The
rectification region stays the table's for every pass, exactly as the board pass already
uses it.

### Attribution

Every detection records the surface supporting it, by the name the world knows that surface
by. `perception-backend` pushes `is_supported_by` down into the search, so what a detection
answers about its own support has to name a world entity rather than a plane height.

### Verification

Tests first, against the rendered scene: `PlacedPiece` gains the height of the surface it
stands on, so a test can stand a piece on the board's lid, and the assertions are that it
is found there, reported at the lid's height, and attributed to the lid -- with a piece on
the table still attributed to the table, and the lid itself still not reported as a piece.

Run with `--noconftest` and the workspace on `PYTHONPATH` where the ORM regeneration is not
wanted, following #202, #205 and #216; #216 recorded that the suite does run in a container
once its dependency set is installed, so the full run is attempted rather than assumed
impossible.

### `detect-per-supporting-surface`: what it took, and the two reasons the plan had not found

Built 2026-08-30 as pull request #221, `2744c23d`. 9 new tests; `153 passed, 1 skipped`
across the ten `test_montessori_*` modules against `144 passed, 1 skipped` on the parent,
which is the nine added here and nothing else changed.

**The item's note says a piece on the lid is "invisible twice over". It is invisible four
times over, and the restructure alone fixes two of them.** The two the plan named -- one
rectification plane, and the board handed to the detector as an obstacle -- are the single
table-plane pass, and the pass-per-surface restructure fixes both. Probing the lid pass
before writing any of it showed it then finding exactly one contour: the lid, with the
cube merged into it, rejected for size. Two further reasons, neither of which the plan
knew about:

- **The lid wears a piece colour.** The board's wood measures at hue 19 and the amber
  prisms at 21, within the four-hue tolerance, so `piece_mask` marked the whole lid.
  Marking every piece colour at once therefore merges a piece standing on the lid into the
  lid's own region, where it has no outline left to measure. Each colour is now segmented
  on its own, which also separates two touching pieces of different colours.
- **A cyan piece and the lid have the same brightness.** With the outline recovered, the
  edge fit still refused it: `EdgeDistances.of` ran Canny over a grayscale conversion, and
  the cube's top face is *one grey level* from the lid while standing 34 apart from the
  bare table. Each colour channel is now read for edges of its own and the results taken
  together, which fits the cube at 0.93 agreement where brightness alone found nothing.

Both fixes stay inside the one detector rather than adding a second, so
`choose-detection-method` still owns choosing *between* detectors. They are here rather
than deferred because without them this item's own claim -- a piece on the lid is found --
is unreachable, and `demo-runs-on-grounded-perception` asks for exactly that in wave one,
before that item exists.

**This weakens one of `choose-detection-method`'s premises.** Its planned rule, "a matte
contrasting surface selects the cheaper colour blob, which works there and is faster", was
motivated partly by the edge fit not working on the lid. It now works there. The rule
needs a different justification -- speed, or the case colour still cannot handle at all:
an amber piece on the wooden lid, which no hue separates from it. Recorded on the tracking
issue as well as here.

**The twin's colour for the board is nominal, not measured.** Reading the surface's own
colour out of the world was considered first, as the knowledge-directed answer, and
rejected on evidence: `BOARD_COLOR` is `Color.BEIGE()`, eleven hues from the wood the
camera measures, so subtracting it would not have subtracted the lid. Moving measured
colours onto the twin's objects is `detector-parameters-from-knowledge`'s ask, and the
board's surface is the same move for surfaces.

**`supporting_surface` is still `None` on every world here, and this item does not
populate it.** `surface-finish-annotation`'s section predicted this item would, and it
does not: the item's claim is the pass structure, `calculate_supporting_surface` is a mesh
ray-cast over a real URDF that cannot be checked from a container, and nothing in this
item needs a declared region. The finish question that section raised therefore does not
arise yet.

**What it costs.** `detect` runs at 0.35 s per frame against the parent's 0.23 s, measured
on this container against the rendered scene. A second surface is genuinely a second pass;
what was avoidable was the hue-saturation-value conversion, which four readings already
duplicated and the per-colour search would have made eight, so the rectified view now
keeps it. The node's `minimum_period` is 0.5 s, so it still fits, with less headroom than
before.

**The environment does run the suite**, as #216 found: Python 3.12, the dependency set
installed into a virtual environment, the vendored `random_events` built from source, and
`urdf_parser_py` copied in by hand. `mujoco`, `manifold3d`, `platformdirs`, `plyfile`,
`lxml` and `daqp` were needed beyond #216's list, and the workspace packages go on
`PYTHONPATH` rather than being installed.

## A capture set, and what it measured (2026-08-30)

Until now the only thing detection could be judged against was a rendered scene
and three `.npz` frames sitting in a session scratchpad. Six rosbags recorded
off the real robot on 2026-08-28 changed that, and one look out of each is now
committed on `montessori-perception-on-main` as a *capture*: the camera's own
compressed colour payload byte for byte, the depth image registered onto it as a
millimetre PNG, and a JSON record of the intrinsics and where the camera stood.
3.0 MB for all six, and a reviewer can open the pictures on GitHub. The rosbags
themselves — 4.7 GB — are gitignored; nothing in the repository can regenerate
them and no review can read them.

Two decisions in that are worth keeping.

**The colour file is the payload, not a re-encoding.** The node subscribes to
`/camera/color/image_raw/compressed`, so JPEG artefacts are what the detectors
see in production. Storing the payload verbatim means a capture and the live
stream hand them the same pixels; re-encoding, or storing a lossless PNG, would
both measure something the robot never sees.

**The captures went on the base of the stack, not the tip.** They are data, and
every branch cut from `montessori-perception-on-main` inherits them — which is
the point of committing them at all. The tests that read them could not follow:
the benchmark needs `supporting_surface`, which only
`detect-per-supporting-surface` introduces, so it sits at the tip while
`test_montessori_captures.py` (the file format itself) sits at the base with the
data.

### What the benchmark says today

Measured over all six, on the merged stack:

- **Every loose piece lying on the bare table is found, with the right
  category, in all six captures.** That is the edge fit of `4b74460f8` doing
  exactly what it was written for, on frames it was not tuned against.
- **A piece standing on the board's lid is reported twice**, once by the lid
  pass and once by the table pass about 50 mm away. This happens in every
  capture that has one, so it is the wider shape of `one-detection-per-thing`'s
  fault: the border boxes were the visible symptom, but the rule "nothing
  forbids two detections occupying one place" fires whenever anything rests on
  the lid at all.
- **Pieces on the lid are lost where they wear its colour or touch each
  other.** `non_inserted_objects` — three pieces crowded together on the lid —
  finds none of them, and the board's own box inflates to swallow them. This is
  `detector-parameters-from-knowledge`'s territory: the hue window and the
  saturation floors are properties of the pieces and the lighting, not of the
  detector.
- **Five of the board's six holes are found, and most are called triangular
  prisms.** This is the largest error, and it has no item yet, so
  `holes-fitted-like-pieces` is new. Loose pieces stopped being classified by
  fill-and-aspect in `4b74460f8`; holes were left on the old
  `CrossSectionClassifier` because they read correctly *then*. They do not read
  correctly in this lighting, and holes are the easier case for the same fit —
  their outlines come exactly from the board mesh, they lie flat in the lid's
  own plane, and the board detection already says where to look.

Each of the three faults has a strict expected-to-fail test naming the item that
owns it, so the day one of those items lands the test reports its own marker as
stale rather than passing quietly. Nothing about the current results is written
into the tests as an expectation: the truth each capture is measured against is
what a reader can see in the picture, and the hole count is read from the board
mesh rather than retyped.

## The ORM has never seen the Montessori package (2026-08-30)

`experiments/src/experiments/montessori/` has no `__init__.py`, on any branch,
so `pkgutil` does not report it as a subpackage and the ORM generator's package
walk skips all of it. Nothing under `experiments.montessori` appears in
`experiments/orm/ormatic_interface.py`. That is the entire cause of the five
`NoDAOFoundError` failures in `test_montessori_insert_shape_action.py` that
`tracy_icra` has carried as "the documented empty-ORM state" — regenerating the
interfaces was never going to fix them, because the classes were never offered
to the generator.

Adding the file was tried and is not a one-liner, so it became
`montessori-classes-in-the-orm` rather than a fix folded in here. Behind it:
`NoSceneAvailable.missing_inputs` was typed `Sequence[str]`, which the generator
cannot resolve (changed to `List[str]`, which every other field in that module
already used), and `perception.footprint.Footprint` collides by name with
`semantic_digital_twin…graph_of_convex_sets.plotting.Footprint`, so the
generator emits two `FootprintDAO` classes and SQLAlchemy refuses the mapping.
Resolving that means renaming one of the two, which is an API change across the
perception package.

Separately, merging main in exposed a genuine call-site break rather than an ORM
one: main's `PickUpAction.object_designator` became a `HasRootBody` and reads the
body off it, so `insert_shape_action.py` passing `montessori_shape.root` raised
`AttributeError`. Fixed by passing the piece. That took the branch from seven
failures to five, and the remaining five are the ORM gap above.

## `perception-backend`: the front door, and what the search is actually told

Kicked off 2026-08-30 in `auto` mode, as pull request #222 off
`perception_per_supporting_surface` (#221).

### It is based on #221, not on #205, and the roadmap already said so

The manifest recorded `depends_on: [surfaces-from-world]`, which would have based this
on #205. That is wrong, and #221's own section above is where it was already settled:
"Every detection records the surface supporting it, by the name the world knows that
surface by. `perception-backend` pushes `is_supported_by` down into the search, so what
a detection answers about its own support has to name a world entity rather than a plane
height." `MontessoriShapeDetection.supporting_surface` exists on #221 and on no earlier
branch, and it is exactly what the supporting-surface pushdown compiles against. So the
dependency was recorded in prose and never in the manifest; `depends_on` now names both.

### The open question the plan left, answered

`PerceptionBackend` subclasses `SelectiveBackend`, which is the answer the roadmap
guessed at ("it selects what is really there rather than inventing it, so probably
yes"). Nothing about a camera makes it generative: it reports what is in front of it and
cannot fill in an attribute nobody can see. Subclassing also inherits the ellipsis guard
for free -- a match with an `...` attribute is refused with the same message a database
backend refuses it with, which is the correct answer for a camera too.

### What the search is told, and what is checked afterwards

The compiled form of a query is a `SceneRequest`: the detection type asked for, and the
supporting surface asked about, both `None`-able. It carries what a *look* can act on
and nothing else.

- **Pushed down**: the selected variable's own type, and a condition of the form
  `<selection>.supporting_surface == <name>`. The pipeline searches one surface instead
  of every surface, and runs the piece detector only when pieces were asked for.
- **Residual**: every other condition over the selected variable. The backend puts the
  detections that came back into the variable's domain and evaluates the expression
  natively, so the entity query language itself does the filtering. Nothing is dropped,
  and nothing needs reimplementing.
- **Neither**: a condition mentioning a variable that is not the one being selected.
  Perception cannot fetch that variable and filtering cannot invent it, so it raises
  `BackendCannotResolveCondition`.

**Correctness never depends on the pushdown being honoured.** The pushed-down conditions
stay in the `where` clause, so native evaluation re-checks them over whatever the source
returned. A source that ignores the narrowing gives the same answers, more slowly. That
is what makes the pushdown an optimisation rather than a second, parallel implementation
of the query's semantics that could disagree with the first.

### The exception goes in krrood, not in the perception package

`BackendCannotResolveCondition` is a statement about the backend protocol -- this backend
translates a query into another engine's plan, and this condition has no place in that
plan -- not a statement about cameras. Any selective backend that translates faces it;
`SQLAlchemyBackend` would face it the moment a condition reached past what SQL can
express. So it sits in `krrood.entity_query_language.exceptions`, beside
`SelectiveBackendCannotResolveEllipsisMatch`, which the item's own note asked for. krrood
gains no dependency on `experiments` from it.

### `Directive.LOOK_FOR`

One member, `KeyWord("Look for")`, beside `FIND` and `GENERATE`. krrood's own test for it
uses a mimic backend in `test/krrood_test/dataset` rather than importing the perception
backend, since `krrood` must stay self-contained.

### The node keeps serving its newest look, deliberately

`MontessoriPerceptionNode` runs the pipeline continuously for rviz and answers a query
from the newest result, which its own docstring records as a decision: "a result that is
one frame old beats blocking a plan on a fresh capture". A request cannot narrow a look
that has already been taken, so the node ignores the narrowing and the residual filter
does the work -- which is exactly the case the paragraph above exists to make safe.

The pushdown is honoured by `MontessoriPerceptionPipeline.detect`, which is where a look
is actually taken. **Worth knowing for `expectations-from-events`:** arming an
expectation ("after `Placing(piece, lid)` search the lid") reaches the pipeline through
the request, so if that item wants the *live node* to look narrowly rather than to filter
its newest full look, that is a change to the node's decision above and its own call to
make.

### `PerceivedObjects` is retired

The item's note asks for it and the plan's "why perception is a backend, not a parser"
section explains it: a domain that runs the whole pipeline on iteration and yields
everything is the opposite of a query running only what it asked for. Its four tests move
to the backend, written the way `test_selective_query_multiple_backends` writes a
SQLAlchemy query -- a variable with no domain, `an(entity(variable).where(...))`, and the
backend supplying the data. That is the point of the item in one line: the same query
text, answered by recall or by looking, depending only on which backend it is handed.

### Verification

Tests first, at three levels, so each failure names its own cause:

- The compiler, on its own: a query with a supporting-surface condition compiles to a
  `SceneRequest` naming that surface and that type; a query with another condition
  compiles to one that narrows nothing; a query over a second variable raises.
- The pipeline, on its own: `searched_surfaces` given a request naming the lid returns
  the lid's search alone.
- End to end over the rendered scene fixture: the four retired `PerceivedObjects` tests,
  rewritten against the backend, plus a residual condition returning the right subset.

Run with `--noconftest` and the workspace on `PYTHONPATH` where the ORM regeneration is
not wanted, following #202, #205, #216 and #221; #216 and #221 both recorded that the
suite does run in a container once its dependency set is installed, so the full run is
attempted rather than assumed impossible.

## `montessori-classes-in-the-orm`: what was actually wrong, and what was not

Kicked off 2026-08-30 in `auto` mode, as pull request #223 off
`montessori_perception_on_main` (#202, open and out of draft, so ready to stack on --
`check_dependency_readiness.py` reports `open_ready`). The mechanical scope check reports
every perception path this touches absent from `main` and shared with #202, #205 and
#221, which every round on this plan has already recorded as expected: every file in this
plan is introduced by #202, so path overlap alone would fold the whole plan into one item.
What remains once the overlapping edits are removed is a package that the ORM generator
has never walked and a class name it cannot map twice -- substantial, and unrelated to
what any of those three branches is about.

The item's branch is `claude/montessori-classes-orm-s7vxu1`, not the
`montessori_classes_in_the_orm` the manifest named: the session was designated that branch,
and the manifest now records what exists rather than what was planned.

### The cause, measured rather than inferred

`classes_of_package(experiments)` yields **87** classes on the parent branch and **154**
with `experiments/montessori/__init__.py` added. `pkgutil.walk_packages` reports a
directory as a subpackage only if it holds an `__init__.py`, so without one the entire
Montessori package -- semantics, world, hole geometry and the whole perception package --
is invisible to every generator, and regenerating the interfaces could never have fixed
the `NoDAOFoundError` failures on `tracy_icra`.

### The collision is real, and the rename is on this side

With the package walked, the generator writes two `FootprintDAO` classes sharing one
`__tablename__`: one for `experiments.montessori.perception.footprint.Footprint`, one for
`semantic_digital_twin...graph_of_convex_sets.plotting.Footprint`, which the dependency
interface already maps. Importing the result raises
`InvalidRequestError: Table 'FootprintDAO' is already defined for this MetaData instance`.
Reproduced before anything was changed, not taken from the note.

Renamed to **`RectifiedFootprint`**, on the perception side, which is the side the item's
own notes anticipated. It is the footprint measured in the metric top-down rectification
the package already names (`orthophoto.py`), and that is also what distinguishes it from
`HoleFootprint`, the footprint the board mesh gives. Keeping the word the module, the
`footprint` field and `FootprintClassifier` already use makes it one identifier rather than
a re-spelling of the package -- which matters here, because #205 and #221 are editing
`pipeline.py` and `footprint.py` at the same time and every renamed line is a conflict they
inherit.

Renaming the `semantic_digital_twin` class instead was considered and not done: it would
reach into another package from an item whose track is "the perception package reaches
main", and #216 is that plan's `semantic_digital_twin` item.

### Two things the item's notes recorded that did not reproduce

- **`NoSceneAvailable.missing_inputs: Sequence[str]` resolves.** The note said the
  generator cannot resolve it, and that it had already been changed to `List[str]`. Neither
  is so on this branch: the field is still `Sequence[str]`, ORMatic normalizes it to
  `typing.List[builtins.str]` and maps it as JSON. No source change is needed and none is
  made.
- **Nothing else was behind those two.** The note allowed for more faults after them.
  With the `__init__.py` and the rename, the class diagram builds and the interface writes.

### Everything the walk newly maps is left mapped

The `__init__.py` brings the perception machinery into the interface too -- `RgbdFrame`,
`Orthophoto`, the detectors, the viewer. Excluding them the way
`experiments/scripts/generate_orm.py` excludes the control-loop benchmarks ("benchmarking
measures a running system instead of describing it") was considered and not done: they map
cleanly, nothing asks for them to be left out, and `detector-parameters-from-knowledge` is
about moving detector parameters onto persisted objects, so an exclusion written now is a
policy this plan would have to undo.

### Verification, and what a container cannot do

`test/experiments_test/test_montessori_orm.py`, written first: the walk offers the
Montessori classes to the generator; no Montessori class shares its name with one
`semantic_digital_twin` maps; and the generated interface resolves a DAO for `CubeShape`
through `get_dao_class`, the lookup whose miss is what raises `NoDAOFoundError`.

**The full workspace regeneration does not run in this container, and that is not this
branch's doing.** `giskardpy`'s generator raises
`CouldNotResolveType: DebugExpressionPublisher` because its ROS 2 executor's annotations
name types nothing here can import, and `coraplex`'s generator imports `geometry_msgs`
before it starts. Both reproduce on the unmodified parent. So the interface the tests read
is built in CI, not here.

What was run here instead is the experiments class diagram with the
`semantic_digital_twin` and `giskardpy` interfaces as its dependencies, which is where both
faults live: it reproduced the duplicate `FootprintDAO` and the import failure exactly, and
is what confirms the fix. `giskardpy`'s own interface had to be built with its ROS executor
classes ignored to get that far -- a scratch harness, not a repository change.

**The environment is worth recording, because the two items before this one recorded a
harder one.** `uv sync --extra dev --python 3.12` builds the whole workspace and every
package imports, including `giskardpy` and `coraplex`. #216's hand-built recipe -- a
virtual environment, `random_events` from source, `urdf_parser_py` copied in -- is no
longer needed.

### Landing hazard

#205 and #221 both edit `pipeline.py` and `footprint.py`, so both conflict with the rename.
The resolution is mechanical: take their edit, spell the class `RectifiedFootprint`.

## Finding the surface by looking, not by being told (2026-08-30)

Raised by the developer while watching the workspace clip: it still shows the floor, the
chairs and whoever is standing at the table, because the region searched is a hand-written
rectangle bigger than the table. Two answers came out of that, and they are different in
kind.

The immediate one is a tool. `tune_workspace` gives each of the workspace's four edges a
slider and draws the clipped camera image, the depth and the rectified table while they
move, so the region can be cut down to the table by eye and written back into the setup.
The sliders can only shrink the declared region, never grow it past what the setup already
searches, so a tuned workspace is always one the camera saw. That fixes the picture, and it
fixes it the way every constant in this plan was fixed before the plan existed: a person
looked and typed a number.

The second is the plan item `surfaces-found-by-looking`, and it is the question this whole
plan asks about pieces, asked about the surface they rest on. **Every surface here is taken
from a model rather than measured** - a constant in `recorded_setup`, or the body's own
collision shape in `surfaces-from-world`. Neither says where the table really is, and this
demo has already drifted away from its own model once: the board and the pieces do not
stand where `montessori_demo`'s hardcoded layout puts them, though the height agreed
exactly. A recording carries no world at all.

So describe the table by what the twin already knows about it - a large horizontal plane,
mirror-finished (`surface-finish-annotation`), colourless, about the modelled size, the
biggest such surface in view - as an entity query language expression, and compile the
detectors that find it from those conditions. That is `choose-detection-method`'s claim
turned on the surface itself, and it is what would make the workspace something the robot
works out rather than something a person tuned.

**Evidence to carry into it, so the failed half is not re-run.** The point-cloud trial
recorded on `tracy_icra` measured a RANSAC plane holding 34% of 693k points on the bare
steel and 69% with a mat, table points scattering about 17 mm either side of it - workable
for the *surface*. The same trial found that no piece stood out of that cloud at all, which
is why pieces are read by fitting known outlines to edges. A plane fit is therefore a
candidate for the table and known not to be one for what rests on it.

From the captures: everything detected across all six lies within x 0.57..0.91 and
y -0.02..0.37, against a searched region of x 0.35..1.35, y -0.45..0.75. The great majority
of what is rectified every frame is floor.

It sits after the deadline's critical path deliberately - the demo runs on a tuned
workspace, and this replaces the tuning rather than unblocking anything.

## `one-detection-per-thing`: no two things in one place

Kicked off 2026-08-30 in `auto` mode, as pull request #225 off
`perception_per_supporting_surface` (#221, open and out of draft, so ready to stack on --
`check_dependency_readiness.py` reports `open_ready`). The mechanical scope check reports
every path this touches absent from `main` and shared with #202, #205, #221 and #223,
which every round on this plan has already recorded as expected: every file in this plan
is introduced by #202, so path overlap alone would fold the whole plan into one item.
What remains once the overlapping edits are removed is an occupancy rule that no earlier
item states in any form, and the detection benchmark #221 shipped already fails for the
want of it.

**The branch is `claude/plan-item-kickoff-kdp-z4pv7l`, not the
`perception_one_detection_per_thing` the manifest named**, following #223: the session
was designated that branch, and the manifest records what exists rather than what was
planned. The session's branch arrived cut from `integration` rather than from anything
this plan is stacked on -- the hazard #199 exists to refuse -- and was reset onto #221's
tip before the first commit.

**It is based on #221's current tip, `df667585e`, not on the `2744c23d` the item's note
records.** #221 has since gained `tune_workspace` and the tuned-workspace file, which is
what the searched region now comes from.

### The fault has two shapes, and the wider one is measured

The item's note names the border boxes: a lid border is a long straight edge, a prism
template fits it at about 0.7, and `board.encloses` rejects only a contour whose *centre*
falls inside the board, which a contour riding the border does not have.

The capture benchmark #221 shipped measured the wider shape. Every capture holding a
piece on the board's lid reports that piece a second time on the table, about 50 mm from
the first: the table pass rectifies a piece standing 80 mm higher onto the table's plane,
where parallax displaces it outward, and the displacement is exactly what carries its
centre out of the board's outline and past `SurfaceSearch.claims`. So both shapes are one
rule missing, and it is the rule the item's title states: nothing may be reported in a
place something else already occupies.

### A place is a volume, not a position

`SurfaceSearch.claims` already asks a question of this kind and asks it of a single point,
which is why a contour riding a border escapes it. The rule here is asked of the space a
detection takes up: its own outline, between the surface it rests on and its own top.
`MontessoriDetection` already reports both heights (`surface_height`, `top_height`) and
its outline in world coordinates, so the volume is a reading of what a detection already
carries rather than anything new measured.

Two volumes are the same place when their outlines overlap in plan view *and* their height
spans overlap. Both halves are load-bearing: a piece resting on the lid stands directly
above the board and shares its outline entirely, and only the height span tells it apart
from a ghost reported inside the board at the table's plane.

### What already occupies a place

- **The board, as it was seen this frame.** It stands from the table up to its lid, so
  anything reported at the table's plane within its outline is either the board's own edge
  or a ghost of something standing on it. The *detected* board is used rather than the one
  the world models, because the world's board pose is known to have drifted from the real
  one -- recorded under "Finding the surface by looking" -- while the board detector
  measures it every frame. This is the same split #221 already made for the lid: its
  height from the world, its extent from the detection.
- **Another detection.** Two detections in one place are one thing seen twice, and the one
  kept is the one with the stronger `outline_agreement` -- already documented as how a
  piece is told from its own reflection, and the measurement that a rectification onto the
  wrong plane degrades.
- **A body the world already knows about**, for the bodies perception is not itself
  measuring: the robot's own links reaching over the table, and whatever else the world
  places in the workspace. The table, the board and the pieces are excluded, since
  perception measures those and the model of them is what has drifted.

### `is_place_occupied` is measured before it is used

`semantic_digital_twin.reasoning.predicates.is_place_occupied` is what the item's note
names for the known-body half, and it answers exactly this question -- but it builds a
trimesh `CollisionManager` over every collidable body on every call, and `detect` already
costs 0.35 s of the node's 0.5 s period. Whether it is affordable per detection per frame
is measured in this container and recorded with the result, rather than assumed either
way. The alternative, if it is not, is the same box-shaped reading of a body the
`WorkspaceSurface` fallback already takes.

### The expected-to-fail mark is this item's to remove

`test_only_the_pieces_resting_on_the_table_are_detected_there` is marked strict
expected-to-fail naming this item, and its module's own docstring says the mark reports
itself stale the day the item lands. Removing it is that contract being honoured, not a
test being changed to pass.

### Verification

Tests first, at three levels, so each failure names its own cause:

- The volume rule on its own, in a new `test_montessori_occupancy.py`: two volumes at one
  position but different height spans are not the same place; overlapping outlines in one
  span are; a weaker detection loses its place to a stronger one.
- The pipeline on the rendered scene, in `test_montessori_perception.py`: a detection at
  the table's plane inside the board's own outline is not reported.
- The captures, as the measurement that matters: the strict expected-to-fail mark comes
  off, and no piece is reported on the table that is not lying on it, in all six.

How much of a shared outline counts as one place is a threshold, and it is measured off
the captures and the rendered scene rather than chosen -- two pieces standing side by side
touch, and their fitted outlines overlap slightly, so the number has to separate that from
a ghost. It is recorded with the value it takes.

Run under the environment #223 recorded, `uv sync --extra dev --python 3.12`, which builds
the whole workspace here.

### Landing hazard

#223 renames `Footprint` to `RectifiedFootprint` across the perception package, and this
branch edits `pipeline.py` and `detections.py`, so it conflicts with that rename the same
mechanical way #205 and #221 do: take this branch's edit, spell the class
`RectifiedFootprint`.

## What the three expected failures actually are (2026-08-31)

The developer's ask: the captures the pipeline still gets wrong are not a general-perception
problem to be solved by a better detector, they are exactly the problem knowledge is supposed
to solve, and they belong in the paper and the demo rather than in a deferred item. A static
picture of a cube lying on a wooden lid may well be unreadable; a picture of *the cube the
robot released over the square hole one action ago* is a different question, and an easier one.

That is right, and measuring it changed three of this plan's items. What follows is what was
measured, on the six shipped captures, before anything was decided.

### The seed is what is missing, not the evidence

`LoosePieceDetector.detect` walks the piece hues, masks, finds contours, and only a contour
that survives the mask, the size range and the wholly-within test is ever handed to
`PieceMatcher.match`. Colour is a gate. A piece wearing the lid's own hue, or touching another
piece, is never fitted at all - however plainly its edges sit in the picture.

Seeding `PieceMatcher.match` by hand at the places the board detection already reports, with no
colour at all, reaches agreements of 0.62 to 0.89 in captures where the bottom-up pass reports
nothing there. `non_inserted_objects` is the extreme: the pipeline reports one detection in the
whole scene and that one is a ghost on the table, while seeded fits at four places on the board
return 0.63, 0.66, 0.78 and 0.85. The evidence is in the image.

It is also cheap. One seeded fit, sweeping position and yaw over all six candidate pieces,
costs 0.05 s; a full bottom-up pass over both surfaces costs 0.25 s. Evaluating a handful of
places the robot has reason to care about is cheaper than the pass that misses them - which
disposes of the obvious objection that expectation-driven search is an extra cost.

### A high score is not evidence of a piece

The same measurement carries a warning that shapes the fix. A triangular prism template laid
near the middle of the board reaches **0.85 to 0.89 in every capture**, converging on the same
spot each time - and there is no triangular prism there. That is higher than every genuine
piece resting on the lid reaches in the same captures, which mostly run 0.64 to 0.71.

So `PieceMatcher.minimum_agreement` cannot be tuned into correctness. Its recorded justification
- a correct piece reaches 0.63 to 0.86 and the best wrong piece of the same colour reaches 0.62
- was measured on the bare table, and near the board the two ranges are the wrong way round.
Agreement measures how well an outline follows *some* edge and says nothing about what put that
edge there. The board is full of sharp edges that a piece template fits.

**A two-plane test was tried and does not work.** Scoring the same outline in the lid's own
rectification as well as in the plane a piece's top stands on ought, in principle, to separate a
hole cut in the lid from a piece standing on it. It does not: the difference falls between +0.30
and +0.62 for holes and pieces alike, in all five captures. Recorded so it is not tried again.

What is left is to ask what else could have produced the edges - which is `competing-explanations`.

### The holes are mislocated, not mislabelled

`holes-fitted-like-pieces` was written as a labelling fault: the classifier calls most of the
holes triangular prisms, so point the piece fit at them instead. Measuring says otherwise.
Placing the board mesh's own six hole footprints at the board pose the detector reports spreads
them over about 180 mm of the lid's length, which is what a 282 mm board says. The five contours
the pipeline currently calls holes sit inside about 90 mm near the board's middle. They are not
the holes.

And the previous paragraph explains why: a per-contour free fit will happily put a prism
anywhere near the board's middle at 0.85. Giving each hole three degrees of freedom of its own
is the fault. The layout is rigid and known exactly, so fitting it as one model - three degrees
of freedom for all six holes together, seeded from the board detection - cannot invent a hole,
cannot put two in one place, and cannot land on the drawer fronts. Each hole's identity then
comes from the model rather than from classifying its contour, so the labelling fixes itself.

That item was rewritten accordingly, and now depends on `pieces-looked-for-where-expected`
rather than running beside it: fitting a known model at a believed pose is the evaluator that
item builds, and two branches independently building the same thing is the duplication these
notes already record twice.

### Only one bag holds the robot

The developer proposed replaying the robot's motions from the rosbags into the simulated world,
running Segmind over the replay, and taking each object's history from the events. The machinery
for that exists and is small - Segmind's `EpisodePlayer` -> `DataPlayer` -> `FilePlayer` takes a
generator of per-frame body poses, and `CSVEpisodePlayer` and `JSONPlayer` are its two current
members - so a rosbag player is one more member and `EpisodeSegmenterExecutor` needs no change.
That is `episode-replayed-into-the-world`, and it touches only Segmind, so it can start now.

**But the recordings do not all support it.** Reading the six bags' metadata: only
`tracy_pickup_demo` carries the robot - `/tf`, `/tf_static`, `/joint_states`, both arms and both
grippers, 150 seconds and 253,000 messages. The other five carry nothing but the three camera
topics over about 29 seconds each. There is no robot motion in them to replay and no transform
tree to read.

This does not sink the approach, and it is worth being precise about why. The three captures the
story is really about - `stuck_cube_in_hole`, `disoriented_cube_on_hole`,
`displaced_cube_from_hole` - are a cube that an insertion put at a *named hole*. A hole is a
place in the world, given by the board mesh and located every frame by the board detection. So
the expectation "the cube is at the square hole, turned some way, resting on or in the lid" is
fully grounded in knowledge the robot already has, with no recording needed at all. The replay
is what gives the *live* demo its history, and what lets the pick-up demo be measured; the five
scene captures are answered by the board and the action model.

Recording `/tf` and `/joint_states` alongside the camera in future takes costs nothing and would
remove the split.

### What changed in the plan

Two new items in the `surfaces` track, one in `events`, and four items widened.

- **`pieces-looked-for-where-expected`** (new). Detection becomes the evaluation of hypotheses
  rather than the classification of blobs. A hypothesis says what is expected, where it is
  believed to be - a region of a named surface and an interval of yaw - and where that belief
  came from; its evaluator is the sweep `PieceMatcher` already performs, with radius, step,
  angle set and candidate list read from the belief instead of fixed. Colour becomes one source
  of hypotheses and one piece of evidence, never a gate. Depends on `one-detection-per-thing`
  and on nothing else, so it is not behind the ripple-down rules.
- **`competing-explanations`** (new). The decision to report becomes a comparison against the
  alternatives - the board's own known geometry, another hypothesis, nothing at all - in place
  of `minimum_agreement`. This is also where the plan's central claim becomes a plottable
  quantity: with one candidate and a strong belief, less picture evidence is needed than with
  six candidates and none.
- **`episode-replayed-into-the-world`** (new). A Segmind `FilePlayer` over a rosbag, with the
  constraint above recorded on it.
- **`holes-fitted-like-pieces`** rewritten, as above.
- **`expectations-from-events`** widened from an expectation that names a surface to one that
  carries a pose belief, propagated by the action's declared effect and confirmed or refuted by
  the events. The rule that carries the weight is that a belief only decays when something acts
  on the object, which is why a history makes tractable what a single frame does not.
- **`choose-detection-method`** widened: the tree's conditions include what has lately happened
  to the target, not only standing properties of it and its surface.
- **`detector-parameters-from-knowledge`** widened: the numbers concluded include the ones that
  say how to search - how far around a believed place, how finely, which candidates, how much
  better one explanation must be than the next.
- **`perception-backend`** gained a note, not a change, since it is under review: `SceneRequest`
  will need to carry a believed place as well as a type and a surface.

**One ownership move worth flagging.** `test_every_piece_resting_on_the_lid_is_found` belonged
to `detector-parameters-from-knowledge`, which is blocked on krrood's ripple-down rules being
usable - the schedule risk already recorded for the 4-8 September window. Those failures are a
seeding fault, not a parameter fault, so the test moves to `pieces-looked-for-where-expected`,
which depends on no rule engine. That takes the plan's most visible remaining error off the
blocked path.

Nothing here is deferred, and the two deferred items are untouched.

### `one-detection-per-thing`: what the fault turned out to be, and the rule that fits it

Built 2026-08-31 as `cf155f4a1` on #225. 23 new tests; `219 passed, 1 skipped, 11 xfailed`
across the montessori modules against `191 passed, 1 skipped, 16 xfailed` on the parent,
which is the 23 added here plus the five captures that stopped failing and nothing else
moved.

**The plan's own account of the fault was wrong, and measuring it changed the design.**
Both this item's note and the section above describe the duplicate as a detection standing
where the board stands -- "a ghost reported inside the board at the table's plane" -- and
propose an occupancy rule over the board's own volume. Measured on the six captures, that
is not where the duplicates are. Every one of them lies *outside* the board's detected
outline, by 14 to 63 millimetres, and shares no ground with it at all: the volume rule as
planned rejects none of them. The real table pieces, for comparison, stand 115 to 186
millimetres clear of the board, so the two populations are cleanly separated but not by the
rule that was written down.

**What they are is the table seen past the board.** A piece standing on the lid is between
the camera and the table behind the board, so the table's own rectification places it there
-- outside the board, along the ray from the camera. That is a statement about line of
sight, not about volume, and it needs the camera's own pose, which the frame already
carries. Projecting the board's outline away from the camera onto the table's plane, cast
from the top of a piece standing on the lid rather than from the lid itself, gives the
stretch of table no detection may claim to be resting on. Measured over the captures, every
duplicate lies wholly inside that stretch and every real table piece wholly outside it.

The height half of the rule earns its place unchanged: what the board hides reaches only up
to its lid, so a piece resting *on* the lid stands above it and keeps its own place, and a
hole lying flat in the lid takes up no space at all.

**No threshold, and none was needed.** The plan expected the shared-outline fraction to be
a measured constant. It is not a constant: two solid things cannot stand in one another, so
any shared ground at meeting heights is one thing read twice. The captures bear that out --
a duplicate shares its whole outline with the ground the board hides, and no two separate
detections share any of theirs -- so the rule is `> 0` and there is nothing to tune.

**`is_place_occupied` was measured and not used.** The item's note names it for the
known-body half. It builds a trimesh `CollisionManager` over every collidable body on every
call, measured here at 0.035 s against the fifteen-body `MontessoriWorld`; six detections is
0.21 s of a 0.5 s node period that `detect` already spends 0.35 s of. Reading every
collidable body's bounding box instead costs the same 0.21 s per pass, so the cost is the
world walk rather than the collision engine. So the rule is applied to the one body actually
in the way -- the board, its identity and height from the world and its extent from the
look, which is the split #221 already made -- and **a general per-frame walk of the world's
bodies does not fit the frame budget**. That is recorded rather than dropped: it is a
finding for `detector-parameters-from-knowledge`, whose ask is exactly which numbers a
situation warrants, and for whoever wants the robot's own arm excluded from the search.

**What it costs: nothing measurable.** `detect` runs at 0.279 s per frame against the
parent's 0.289 s, over the six captures. The rule is one convex-polygon intersection per
detection.

**The expected-to-fail mark came off five captures of six**, which is the contract the
benchmark module's docstring states. `non_inserted_objects` keeps it, now naming
`holes-fitted-like-pieces` rather than this item, and the reason is measured: the board is
reported at -29.7 degrees there against -7.6 degrees in the other five, about the same
centre (0.791, 0.128 against 0.794, 0.138), because `_board_around` orients the lid
rectangle by `minAreaRect` over the hole centres and only five of the six holes are found.
With the board at the orientation the other five agree on, that capture's reading falls
inside the ground the board hides. So the rule is right there too, and what is wrong is the
board's own pose.

**Two smaller things worth knowing.** `RgbdFrame` gained `camera_position`, since where the
camera stands is what casts the shadow and every caller was reaching into
`reference_frame_T_camera` for it. And the session's branch arrived cut from `integration`
rather than from #221 -- the hazard #199 exists to refuse -- and was reset onto #221's tip
before the first commit.

### `perception-backend`: the review round of 2026-08-31, and the two things it reversed

Resolved 2026-08-31 in `auto` mode. **Nothing was wrong with the branch.** #222 was green on
all 23 checks, `mergeable_state: clean`, both dependencies open and out of draft, and no
upstream pull request (no `in-review` label). What kept it open was nine unresolved review
threads opened that morning, of which the item's own `blockers` recorded none — the third
time on this plan that the cause of a stall was a review comment nobody had turned into
state. Writing them down was the first thing this resolve did, before any code.

**Two of the threads reversed decisions this roadmap had recorded as settled**, and both
reversals are the developer's, taken as answers to questions this session put to him rather
than as calls it made.

#### Generative, not selective

The roadmap recorded the family question as the open question this item settled, and settled
it as `SelectiveBackend`: "a camera reports what is in front of it and cannot fill in an
attribute nobody can see". The developer reopened it and the reasoning that won is his: *with
the instances already believed in we are only asking perception for the pose, which is an
underspecified statement; with no belief yet, the look is what brings the instance into
existence.* Neither is selection from a domain the statement was handed, so the backend is a
`GenerativeBackend`.

This session recommended staying selective and was overruled. Recorded because the
recommendation was wrong in an instructive way: it argued that nothing in the item exercises
the generative case yet, which is true of the *tests* and false of the demo — asking where a
known hole is, is precisely the pose-only question, and it is what `expectations-from-events`
and `pieces-looked-for-where-expected` were already being written around.

The shape of a statement changes with it, from a query over a domain to a `Match`:

```python
an(MontessoriShapeDetection)(supporting_surface=lid_name, pose=...)
```

**An attribute stated as `...` narrows nothing and rejects nothing.** It is the statement
saying the look must supply it, which is the whole point of the pose-only question.

#### The general half belongs in krrood

The roadmap recorded the opposite — the backend in `experiments`, with only the exception, the
condition reader and the `Directive` member in krrood — and the developer rejected it twice:
*"why did you put this in experiments? why not in EQL itself? … Because I would like this to
work also outside the montessori demo generally."*

`PerceptionBackend` and `LookRequest` now sit in `krrood.entity_query_language.backends` beside
the other backends and carry everything about how a statement is read, narrowed and checked.
`MontessoriPerceptionBackend` carries only what is particular to this scene: that a look is
taken by the Montessori pipeline, and that its search narrows by the surface a detection rests
on. krrood gains no dependency on `experiments`, and its own tests use the mimic
`BackendThatLooksAtTheWorld` in `test/krrood_test/dataset/`.

#### Two measurements the redesign turned up

Both were assumptions until they were run, and both would have shipped wrong answers:

- **Native evaluation returns nothing at all for a `Match` carrying an ellipsis attribute.**
  `an(Sighting)(place="lid", pose=...)` over a domain holding the right sighting yields `[]`,
  because `...` means *construct this* and selection cannot satisfy it. So the ellipsis
  attributes have to be dropped from the check and the stated ones re-applied, rather than the
  match simply being evaluated over what the look found.
- **Native evaluation does not narrow a domain by the variable's declared type.**
  `an(SpecialThing)()` over a domain of mixed `Thing` and `SpecialThing` returns all of them.
  The old selective code did this filtering itself via `SceneRequest.admits`; the general
  backend does it now via `LookRequest.admits`, and `SceneRequest.admits` was left dead by the
  move and removed.

#### What was deliberately not built

The other five threads are one ask — narrow a look by what the world means, not by an attribute
spelled as a string — and they became **`perception-predicates-guide-the-search`**, stacked on
this item. That placement is the developer's own on r3893312001: *"you can make this a separate
PR that this one here is stacked under."* Until it lands,
`SUPPORTING_SURFACE_ATTRIBUTE_NAME` remains a string, guarded by a test asserting it is a real
field of the detection. The sixth thread, r3893463818 (perception algorithms declaring the
requests they can answer, with a reasoner choosing between them) is recorded on
`choose-detection-method`, whose claim it restates from the detector's end.

#### The round could not be replied to

**All nine threads are left open and none is resolved**, including the five whose work is
done. The developer has an unsubmitted **pending review** on #222 (review `5064626804`, on
commit `71730494`), and GitHub allows one pending review per user per pull request; the API
acts as that same account, so every inline reply is refused with *"user_id can only have one
pending review per pull request"*. Resolving a thread without an inline reply on it is
forbidden by the standing conventions, so nothing was resolved. Submitting or discarding that
draft review unblocks the whole round — the code the threads asked for is already pushed.

Worth generalizing: a pending review by the same account the tooling authenticates as blocks
*every* inline reply on that pull request, not just replies to its own comments. It is
invisible in the pull request's own state (`mergeable_state` is clean, CI is green) and shows
only as `state: PENDING` in the reviews list.

#### Verification

`test/experiments_test/`: **362 passed**, 1 skipped, 16 xfailed, against **348 passed** on the
parent, no failures either side. `test/krrood_test/test_eql/`: **1087 passed** against
**1072**, with a failing-and-erroring set byte-identical to the parent's — 177 lines on both,
diffed by name rather than compared by count, following what `surface-finish-annotation`
recorded about generated files making count comparisons lie.

**One way that comparison nearly lied again, worth recording.** The parent baseline was first
run in a `git worktree`, which reported the same 177 errors and looked convincing. It was
meaningless: `uv sync` installs the workspace editable, so the worktree's `python` imported
`krrood` from the *main* checkout — the branch's own source — and the "parent" run was the
branch's code against the parent's tests. The fix is to put the worktree's own `*/src` on
`PYTHONPATH`, and to check `krrood.__file__` before trusting any baseline taken outside the
main checkout.


## Two items that meet at one type (2026-08-31)

`pieces-looked-for-where-expected` and `perception-predicates-guide-the-search` were added the
same day by two sessions, neither able to see the other's. They are not duplicates, but they end
at the same thing and would each have built it.

- `perception-predicates-guide-the-search` comes from #222's review: a look should be narrowed by
  what the world *means* - support, `LeftOf`, a colour - so a spatial predicate is read as a
  `Region` with extents and the image clipped to it before anything is detected.
- `pieces-looked-for-where-expected` comes from the capture measurements: detection becomes the
  evaluation of hypotheses, each carrying a believed place - a region of a named surface and an
  interval of yaw - which the piece matcher's sweep is parameterized by.

The shared thing is the believed place. One says where it comes from, the other what is done with
it. **It is defined once, in `pieces-looked-for-where-expected`**, and the predicate item supplies
it; the sequencing follows from the tracks they already sit in, since that item is in `surfaces`
and waits only on `one-detection-per-thing`, while the predicate item waits on
`perception-backend`.

Recorded because this repository has twice built one artifact under two items that could not see
each other - #110 against #106's `POINTER.md`, and #117's fold into #106 - and the cost is only
avoidable before either branch is cut. The imagination-world rejection sampler is the predicate
item's alone and duplicates nothing here.

## `perception-predicates-guide-the-search`: the plan, and the two thirds it deliberately leaves

Kicked off 2026-08-31 in `auto` mode, as pull request #227 off `perception_eql_backend`
(#222, open and out of draft, so ready to stack on -- `check_dependency_readiness.py`
reports `open_ready`). The session's branch arrived cut from `integration` rather than
from #222 -- the hazard #199 exists to refuse, and the third time on this plan after #223
and #225 -- and was reset onto #222's tip before the first commit.

The mechanical scope check reports three of the five paths this touches absent from `main`
and shared with #222, which every round on this plan has already recorded as expected. What
remains once #222's own edits are removed is a predicate vocabulary in
`semantic_digital_twin` and a narrowing mechanism in `krrood` that no earlier item states in
any form, so this is ordinary stacking -- and it is the developer's own placement on
r3893312001: *"you can make this a separate PR that this one here is stacked under."*

### One of the five threads is still open, and it is this item

The item's `blockers` record five threads on #222 deliberately left open. Four have since
been resolved by the developer; the one still open is r3893312001 with its two follow-ups,
which is this item's own ask. Recorded because the item's inherited description of #222's
review state was stale by the time this started.

### What the string actually was, and what replaces it

`SUPPORTING_SURFACE_ATTRIBUTE_NAME = "supporting_surface"` exists because #222's narrowing
is expressed over *attribute names*: the general `PerceptionBackend` hands a subclass a
`LookRequest`, and with the narrowing spelled that way a string is the only thing the
subclass has to say which attribute its look can act on. The mimic's `PLACE_ATTRIBUTE_NAME`
is the same fault in the same place. Changing the mechanism is what removes them; a better
constant would not.

A predicate is its own source of truth, so a look narrowed by one has no name to spell
twice. `LookRequest` carries the predicates a statement states about the thing sought
alongside the attribute equalities it already carries, and a backend asks for one **by
predicate type** rather than by attribute name.

**The pushdown reads the operand that is already concrete.** A statement says
`SupportedBy(<the thing sought>, <the lid the world knows>)`: the sought thing is the
query's variable and has no value yet, and the supporting entity is a world entity that
does. So the search can be narrowed before anything has been detected, by reading the
concrete operand -- which is exactly what `supporting_surface == <name>` was doing, stated
in the world's vocabulary instead of an attribute's.

### Deliberately not built here, both recorded rather than silently dropped

- **A spatial predicate read as a `Region` with extents**, clipping image and depth before
  anything is detected (r3893602153). "Two items that meet at one type" above already
  settled that the believed place is defined once, in `pieces-looked-for-where-expected`,
  and supplied by this item. That item is `not_started` and depends on
  `one-detection-per-thing` (#225, still a draft), so the type does not exist yet and
  building it here would build it out of order and twice -- the exact duplication these
  notes record three times over. The sequencing the roadmap assumed (that item first) has
  been overtaken by this item being kicked off now, which is why this is a deferral rather
  than a wait.
- **The imagination-world rejection sampler** (r3893499716) -- detect what the other
  conditions reach, spawn the instances into a copy of the world, evaluate the predicate
  there against real `Body` and `SemanticAnnotation`s, delete what it rejects. It is this
  item's alone and duplicates nothing, but it is a second pull request's worth of work, and
  the plan's budget section directs every item to the narrowest form that demonstrates its
  claim. Proposed as its own plan item on #201 rather than widening this branch.

What is left is the claim itself in its narrowest honest form: a look is narrowed by what
the world means, not by an attribute spelled as a string, and both strings are gone.

### `InsideOf` is a value, not a truth

`Predicate.__call__` returns a truth value and `Predicate.__bool__` evaluates it, so the
relations that already return `bool` -- `LeftOf`, `RightOf`, `Above`, `Below`, `Behind`,
`InFrontOf` -- become `Predicate`s directly. `InsideOf.__call__` returns a containment
ratio, and three call sites across `coraplex`, `segmind` and
`semantic_digital_twin.semantic_annotations` read that ratio and compare it to a threshold
of their own. It is a value operation, so it becomes a `SymbolicFunction` -- the other
concrete kind of `SymbolicCallable` -- which keeps `__call__` returning the ratio and every
one of those call sites working. Making it a `Predicate` would have meant either changing
what it returns, breaking all three, or a `Predicate` that does not return a truth value.

`Verbalizable._verbalization_fragment_` is abstract, so every relation that becomes a
`SymbolicCallable` has to supply its clause; a missing one fails at instantiation rather
than only when something is verbalized.

### Verification

Tests first, at three levels, so each failure names its own cause:

- The vocabulary, in `semantic_digital_twin`: each relation is a `Predicate` (asserted
  against the class, not a name), evaluates as it did before, and verbalizes.
- The narrowing, in `krrood`: a statement stating a predicate about the thing sought
  compiles to a `LookRequest` carrying it; a backend reads it back by predicate type; a
  statement stating none narrows nothing. Driven through the existing mimic
  `BackendThatLooksAtTheWorld`, whose `PLACE_ATTRIBUTE_NAME` this removes, per krrood's
  self-containment rule.
- The Montessori backend, end to end over the rendered scene: the same queries #222's tests
  ask, written with a support predicate instead of an attribute equality, returning the same
  answers -- and `SUPPORTING_SURFACE_ATTRIBUTE_NAME` gone, with the test that guarded it
  gone with it rather than left asserting a constant that no longer exists.

Run under the environment #223 recorded, `uv sync --extra dev --python 3.12`, which builds
the whole workspace here.

### Landing hazard

#223 renames `Footprint` to `RectifiedFootprint` across the perception package. This branch
does not touch `footprint.py` or `detections.py`, so it should not inherit that conflict,
unlike #205, #221 and #225.
## A predicate answers whether it holds, and three items to carry that (2026-08-31)

The developer's direction, given after #227 was pushed, and it overturns a decision that
branch made. Recorded here rather than only in the pull request, because it changes what
`semantic_digital_twin`'s predicate vocabulary is for.

### The call #227 got wrong

#227 made `InsideOf` a `SymbolicFunction` rather than a `Predicate`, reasoning that
`Predicate.__call__` must answer a truth value while `InsideOf` answers a containment
ratio that three call sites compare against thresholds of their own. That reasoning is
correct about the mechanism and wrong about the intent: *inside of* is a relation, and a
relation belongs in the vocabulary a statement can assert.

**A threshold field is what reconciles the two**, and it is the developer's own answer:
`__call__` returns a truth value, the ratio is read from a method of the class, and a
threshold with a default decides the one from the other. The callers that want the number
keep it; a statement that wants the relation gets a predicate it can state. Nothing is
lost on either side, which is why the earlier trade-off was a false one.

### It is not only `InsideOf`

The same shape is everywhere in `reasoning/predicates.py`. `is_body_in_region` answers the
same kind of fraction. The truth-valued relations - support, contact, visibility,
reachability, occupancy - are `@symbolic_function`s, so they can be *evaluated* and not
*stated*, which is exactly what r3893312001 asked to change ("used to devise the search
rather than merely evaluated"). A function has no class for a statement to name.

krrood already has the way to do this without breaking anything:
`symbolic_callable_to_function` builds the function spelling from the class, so one
implementation serves both and no call site in `coraplex`, `segmind` or `giskardpy` has to
move.

### Where it lands

**Its own pull request off `main`**, at the developer's direction, and the placement
`surface-finish-annotation` already set: this is a change to the digital twin's vocabulary,
not to perception. The knowledge-directed items that need it merge it in rather than
waiting for it to land, which is this plan's standing `depends_on` rule.

#227 is the first of those. It carries the `InsideOf` change this item overturns, so that
branch drops its own and takes this one in - which is why
`perception-predicates-guide-the-search` now depends on it.

### The two mechanisms #227 deferred are items now

Both were proposed on #201 when #227 was kicked off, and the developer accepted them.

- **`search-clipped-to-a-predicates-region`** (r3893602153) - a spatial predicate read as a
  `Region` with extents, so image and depth are clipped before anything is detected. Waits
  on `perception-predicates-guide-the-search` for the reading of a statement's predicates
  and on `pieces-looked-for-where-expected` for the believed place, which "Two items that
  meet at one type" settled is defined once, there.
- **`imagination-world-rejects-what-a-predicate-refuses`** (r3893499716) - detect what the
  other conditions reach, spawn what was found into a copy of the world, evaluate the
  predicate there against real `Body` and `SemanticAnnotation`s, delete what it rejects.
  This is what closes the gap #227 leaves: a look reports sightings rather than the things
  a relation is written over, so #227 refuses any relation its backend did not narrow by.
  Spawning gives every other predicate a real subject to be evaluated against.

### `predicates-answer-whether-they-hold`: what it took, and where the boundary fell

Built 2026-08-31 as pull request #229 off `main`, and merged into #227 the same day.

**Nine relations converted, not one.** The item was raised about `InsideOf`, and the same
shape turned out to be everywhere in `reasoning/predicates.py`: `is_body_in_region`
answered the same kind of fraction from a name that reads as a question (now
`InsideRegion`), and support, contact, visibility, reachability, stability and occupancy
were `@symbolic_function`s, so they could be evaluated but never stated. The six
view-dependent spatial relations came across from #227's own commit.

**No call site outside the module had to move**, which is what made the scope affordable.
krrood's `symbolic_callable_to_function` builds each function spelling from its class, so
`is_supported_by`, `contact`, `visible`, `reachable`, `stable`, `is_supporting`,
`is_place_occupied` and `is_body_in_region` keep their names and signatures off one
implementation. `giskardpy`, `coraplex` and `segmind` are untouched, which matters because
none of the three can even be imported in this container.

**Two call sites did change, and both for the reason the item exists**: they read a ratio
as a truth value. `semantic_annotations.doors` compared `InsideOf(...)() > 0.1` and now
states `minimum_containment_ratio=0.1`; the procthor script now reads
`compute_containment_ratio()` explicitly. That is the threshold moving from an unexplained
constant at the call site to a stated intent on the relation, which is the whole point.

**Where the boundary fell.** `get_visible_bodies` and `occluding_bodies` answer lists and
`compute_euclidean_planar_distance` answers a distance with no truth reading, so they stay
functions. A predicate is the wrong shape for them, and "everything in the file" would have
been a worse rule than "everything that asserts something".

**A default threshold is a judgement, so it is stated rather than inherited.**
`minimum_containment_ratio` and `minimum_contained_fraction` default to half - a thing more
than half swallowed is in, one less than half swallowed is overlapping. That is a choice
this item made and can be argued with; it is written on the field rather than left for a
reader to infer, and no existing caller depends on it, since the two that thresholded did
so explicitly.

**Verified**: `test_predicates.py` 24 passed against 8 on `main`, and the whole
`semantic_digital_twin` package's failing-and-erroring set byte-identical to `main`'s,
diffed by name in a worktree with its own `*/src` on `PYTHONPATH`.

**Merged into #227 rather than waited on**, which is this plan's standing `depends_on`
rule. That merge took #229's side of `predicates.py` and `test_predicates.py` whole, since
it supersedes what #227 had written, and kept only #227's own test that reads a support
relation asserted about a variable as a `StatedRelation`.

### `predicates-answer-whether-they-hold`: the resolve of 2026-08-31, and the duplicate nobody had seen

The item stalled on a review question rather than on its code: *"I feel this is duplicate with
the smedt migration verbalization PR in the verbalization plan and the migration from
symbolic_callable, can you verify that and discuss what's the best move."* Verified, and the
answer is yes.

**#33 has been doing this migration since 2026-07-06.** `eql-symbolic-function-sdt`, the
`p4-sdt-migration` item of the `eql-verbalization` plan, converts the same
`reasoning/predicates.py` off `@symbolic_function` onto `Predicate` / `SymbolicFunction`
classes, by the same `symbolic_callable_to_function` mechanism, and reaches further:
`queries.py` and `robot_predicates.py` as well, plus `phrase()` in krrood's `parts_of_speech`,
`ORMatic.from_package(ignored_base_classes=...)`, the generated verbalization snapshot wired
into sdt's `conftest.py`, and a 36-thread wording review of which 34 are settled. Every
relation this item converted, that branch had already converted. Both even write
`reachable = symbolic_callable_to_function(Reachable)` over the same class body.

**What is genuinely this item's** is what it was raised for and nothing more: the threshold
field that lets a ratio-computing relation answer a truth value, which #33 does not have -
its `InsideOf.__call__` still returns a float and `is_body_in_region` is still a
`BodyInRegionFraction` `SymbolicFunction` - and the use of krrood's `Triple` as a base.

**Why neither plan saw it.** Nothing in either manifest names the other: this plan's items
were written about perception and sdt's vocabulary, `eql-verbalization`'s about verbalization
surfaces, and `check_scope_overlap.py` was never run for this item because its kickoff read
it as a change off `main` with no unlanded parent - which is true of the path check
(`paths_absent_from_base` is empty) and false of the purpose check the same document asks
for. That is the failure mode "Compare by purpose, not only by path" exists to catch, and it
is the third duplicate this repository has recorded after #110/#106 and #117/#106.

**The resolution is the developer's**, and is put to him on #229 rather than taken here,
because it decides which branch survives and therefore which set of wordings the repository
gets. The recommendation made: let #229 carry the predicate classes and rebase #33 onto it,
porting #33's reviewed wordings across as part of that rebase - on the grounds that #33 is
166 commits behind `main`, `dirty` in `predicates.py` specifically and labelled
`needs-resolution`, so it owes that rebase either way and meets #229's version of the file
whichever order the two land in; while #33's two open decisions block it and do not block
this, so folding the other way would put this plan's 2026-09-15 deadline behind them for no
gain.

#### Two faults this resolve found and fixed

**CI was red and it was this branch's, against what its own description claimed.** Renaming
`SupportedBy`'s fields to `supported` / `supporting` broke
`semantic_annotations/mixins.py:942`, which calls `is_supported_by` by keyword and which the
branch does not touch: five tests in `test_reasoning_queries.py` failed with `TypeError:
SupportedBy.__init__() got an unexpected keyword argument 'supported_body'`. The branch's
verification had diffed the failing set by name locally, where that module cannot be
collected at all - it imports `kitchen_environment`, which imports `rclpy` - so a local diff
was structurally incapable of seeing it and reported clean. **A local failing-set diff is
only evidence for the modules the container can collect**; the ROS-dependent ones are CI's to
answer. Fixed by moving the one call site, with an AST sweep over every call to the nine
migrated relations confirming it was the only stale keyword caller. #227 carries the same
commit and had the same breakage.

**The `Triple`-derived wordings are ungrammatical, and nothing catches them.**
`Triple._verbalization_fragment_` reads the verb off the class name, and four of the names
this branch chose are not verb-first, so they render as *"a Body supports by another Body"*,
*"a Body or a Region visibles to a Camera"*, *"a Body is in a contact with another Body"* and
*"a Body supports a something"*. sdt has no verbalization snapshot on `main` - that test is
one of #33's additions - so no assertion in the suite reads a sentence. Left standing
deliberately rather than fixed: #33 already has correct, reviewed wordings for all four, and
writing a third set before the fold question is settled would be one more copy of the
argument the fold exists to end.

The `Reachable` thread (r3896606294, *"Pose Is reachable by Tip"*) was implemented as asked -
the pose is the subject now, with a test stating the sentence - and left open, because #33's
settled decision 11 words the same relation differently and only the developer can say which
stands.

#### The fold, settled: #229 carries the classes and #33 rebases onto it

The developer's decision, 2026-08-31, taking the recommendation above. This branch keeps
the predicate classes; **`eql-verbalization`'s `p4-sdt-migration` (#33) rebases onto the
main that carries them**, drops its own copy of the `predicates.py` migration, and
re-applies its 34 reviewed wordings onto these classes. Everything genuinely #33's
survives that rebase: `queries.py`, `robot_predicates.py`, `phrase()` in krrood's
`parts_of_speech`, `ORMatic.from_package(ignored_base_classes=...)` and the generated
verbalization snapshot wired into sdt's `conftest.py`.

The reasoning is about which rebase is cheaper rather than which branch is better. #33 is
166 commits behind `main`, `mergeable_state: dirty` in `predicates.py` specifically, and
labelled `needs-resolution`; its own roadmap already says it needs that rebase before any
of its checklist can start, so it owes it either way and meets this branch's version of
the file whichever order the two land in. #33's two open decisions - the type-level
display noun for *"a Point3"*, and widening the IK chain for `Pose` - block it and do not
block this, so folding the other way would have put this plan's 2026-09-15 deadline behind
them for no gain, since #227 needs the vocabulary rather than the wordings.

**The four ungrammatical wordings were fixed here rather than left for that rebase**, also
at the developer's direction, by taking the sentences #33's own review had already settled:
*"a Body is supported by another Body"*, *"a Body or a Region is visible to a Camera"*, *"a
Body is in contact with another Body"*, *"a Body is supporting a body"*. That is one set of
sentences carried across rather than a third set invented - which is the whole point of
settling the fold before either branch lands.

Worth keeping for whoever runs #33's rebase: `Triple` derives its verb from the class name,
so a relation named for its object (`SupportedBy`, `VisibleTo`, `InContactWith`) must state
its own clause. Inheriting `Triple` and saying nothing is what produced *"a Body supports by
another Body"*, and nothing in sdt's suite on `main` reads a sentence to catch it - the
snapshot test that would is one of #33's own additions.

## `pieces-looked-for-where-expected`: the seed, and where a believed place is defined

Kicked off 2026-08-31 in `auto` mode, as pull request #232 off
`claude/plan-item-kickoff-kdp-z4pv7l` (#225, open and out of draft, so ready to stack on
-- `check_dependency_readiness.py` reports `open_ready`). It is based on #225's current
tip `a35243e8`, not on the `cf155f4a1` the item's note records. The session's branch
arrived cut from `integration` rather than from #225 -- the hazard #199 exists to refuse,
and the fourth time on this plan after #223, #225 and #227 -- and was re-cut onto #225's
tip before the first commit.

The mechanical scope check reports every path this touches absent from `main` and shared
with #225, #222, #227 and #223, which every round on this plan has already recorded as
expected: every file in this plan is introduced by #202, so path overlap alone would fold
the whole plan into one item. What remains once the overlapping edits are removed is a
believed place, a hypothesis over it and a matcher parameterized by one, which no earlier
item states in any form. The purpose check matters more than the path check here and it
comes back clean: #227 deliberately did *not* build the believed place, deferring it to
this item, which is what "Two items that meet at one type" settled.

### Colour is a gate, and that is the whole fault

`LoosePieceDetector.detect` walks the piece hues, masks, finds contours, and only a
contour that survives the hue mask, the size range and the wholly-within test is ever
handed to `PieceMatcher.match`. A piece wearing the lid's own hue, or touching another
piece, is never fitted however plainly its edges sit in the picture. So the fix is not a
better mask: it is that a fit may be seeded from something other than a blob.

### What is built, and the three places a belief comes from

- `BelievedPlace` -- a region of a named surface and an interval of yaw. The type
  `perception-predicates-guide-the-search` compiles its spatial predicates *to* and this
  item's search reads *from*, defined here once as that item's own deferral asked.
- `PieceHypothesis` -- what is expected, where it is believed to be, and where the belief
  came from. Its evaluator is the sweep `PieceMatcher` already performs, with radius,
  step, angle set and candidate list read from the belief instead of fixed.
- Three sources, which is what makes this knowledge-guided rather than a wider search: a
  colour blob (as today), the board's own detected holes, and the pieces the world already
  places in the workspace. The object's own history is the fourth and is
  `expectations-from-events`, where a belief gets a pose and an uncertainty.

Colour becomes one source of hypotheses and one piece of evidence for them, never a gate
that can suppress one.

### What this item cannot do, and must not be read as doing

The same measurement that found the missing seed found its hazard: a triangular prism
template laid near the board's middle reaches **0.85 to 0.89 in every capture** with no
prism there, higher than any genuine piece resting on the lid. So seeding at the places
the board reports will produce ghosts as well as the pieces it recovers, and no threshold
separates them -- `PieceMatcher.minimum_agreement` cannot be tuned into correctness near
the board. Deciding a detection by what else could have produced the edges is
`competing-explanations`, which depends on this item precisely because this item is what
turns a detection into a hypothesis that can be compared against another.

What this item is therefore measured by is the recall side: `test_every_piece_resting_on_
the_lid_is_found`, whose assertion is a subset test, and whose expected-to-fail marks this
item took ownership of from `detector-parameters-from-knowledge`. The false-positive count
per capture is measured and recorded with the result rather than left unstated, and a
regression of `test_only_the_pieces_resting_on_the_table_are_detected_there` -- which is
an exact test -- is a blocker to report, not something to absorb.

### Verification

Tests first, at three levels, so each failure names its own cause:

- The types on their own: a place believing a yaw offers only the turns its interval
  holds, one believing none offers the piece's whole rotation period, and a hypothesis
  records the belief it came from.
- The matcher on its own: it searches the radius the belief states, tries only the
  candidates it names, and returns a fit seeded where colour segmented nothing.
- The pipeline over the rendered scene and then the captures, which is the measurement
  that matters: a piece on the lid wearing the lid's own hue is found.

Run under the environment #223 recorded, `uv sync --extra dev --python 3.12`.

### Landing hazard

#223 renames `Footprint` to `RectifiedFootprint` across the perception package, and this
branch edits `pipeline.py`, `detections.py` and `piece_matcher.py`, so it inherits that
conflict the same mechanical way #205, #221 and #225 do: take this branch's edit, spell
the class `RectifiedFootprint`.

### `choose-detection-method`: what it took, and the two things measuring changed

Built 2026-08-31 as `69f30348a` on #231. 25 new tests; `230 passed, 1 skipped, 16 xfailed`
across the montessori modules against `205 passed, 1 skipped, 16 xfailed` on the parent,
which is the 25 added here and nothing else moved.

**Both shapes were built, layered, and the layering is what the scene actually needs.**
The developer chose both at kickoff, and building it bore the reasoning out: each detector
declares the looks it can answer as an entity query language condition, and the rule tree
chooses among the ones that can. The planned third rule -- a target wearing the surface's
own hue falls back to the edge fit -- turned out not to be a rule at all but the colour
blob's own capability going false, so the tree ships the two rules the budget section asks
for and the amber-on-wood case needs nothing written for it. That is the layering paying
for itself rather than costing: a capability is not a weaker rule, it is the half that says
what a detector is *for*.

**Speed is the honest reason, and it is measured.** On the same frame, the same surface and
the same candidates: the colour blob costs **89 ms** against the edge fit's **126 ms**, and
reports the same three pieces at comparable agreement (0.807/0.652/0.926 against
0.829/0.716/0.926), the cube on the lid at 0.926 from both. #201's comment of 2026-08-30
left this item to choose between *speed* and *the case colour cannot handle at all*; both
are taken, because they are one pair of rules read from either end, and the second falls out
of the capability rather than needing a rule.

#### Splitting a surface between two detectors costs a second pass, and that had to be paid for

The first working version was **slower annotated than unannotated** -- 0.596 s/frame against
0.521 -- which is the opposite of the item's claim. The cause is structural rather than
incidental: choosing per piece means the lid is searched once by each detector, and each
detector rectified its own planes and read its own edges off them. The saving is per piece;
the duplicated work is per pass, and on this scene the second pass outweighed it.

`RectifiedFrame` rectifies each plane and reads its edges once per frame, however many
detectors ask for them, and the detectors are handed the edges rather than computing them.
That takes the annotated path to **0.494 s/frame against 0.491 unannotated** -- the split is
now free -- and it made the *unannotated* path faster too, from 0.521 to 0.491, because the
board pass and the lid pass had always rectified the same plane twice.

Worth generalizing beyond this item: the moment a look is answered by more than one
detector, anything derived from the picture rather than from a detector's own parameters
belongs to the frame and not to the detector. `detector-parameters-from-knowledge` moves the
parameters the other way, onto the objects, and these two moves are the same boundary drawn
from opposite sides.

#### The recorded blocker was three facts, and only one of them is about this item

The item's notes and #201's comment of 2026-08-29 record that krrood's ripple-down rules are
"not usable yet", expected to become so through the RDR/EQL refactor's integration build, and
name it as the schedule risk for the 4-8 September window with
`detector-parameters-from-knowledge` behind it. Measured before anything was planned:

- **The classic `krrood.ripple_down_rules` machinery is not usable, as recorded.** Its
  conditions are Python *source strings* (`Rule.conditions: CallableExpression`, parsed from
  an expert's typed text) and every tree-mutating entry point -- `fit`, `update_start_rule`,
  `add_rule_for_case` -- requires an `Expert`. No test in that suite builds a tree
  programmatically; they replay recorded JSON answers through `Human(load_answers=True)`, and
  the whole suite skips when the UCI zoo dataset is not cached.
- **`EQLSingleClassRDR` is not usable either**, and it is what the "integration build" refers
  to: it lives on `D-core-single-class`, eight unmerged pull requests deep in a stack whose
  root (#64) is still open against `main`.
- **The EQL-native rule trees are usable today, on `main`.** `refinement()`, `alternative()`,
  `next_rule()`, `add()` and `inference()` in `krrood.entity_query_language.factories` build a
  tree in a `with query:` block, and `ConclusionSelector.insert_at` grows one without one.
  Their conditions are genuine `SymbolicExpression`s, `Predicate`s included -- which is what
  the item's own note describes. `test/krrood_test/test_eql/test_core/test_rules.py` is
  **24 passed** here, no skips and no xfails.

So the item was never blocked, and neither is `detector-parameters-from-knowledge` behind it.
Recorded at this length because the same sentence was carried on two items and on the
tracking issue for two days, and it was three claims of which only the first two are true.

#### Two smaller things the build settled

- **A conclusion has to be hashable.** The rule tree concludes the pipeline's own detector
  *instances* rather than constructing fresh ones, so the detectors are `@dataclass(eq=False)`
  -- a value-comparing dataclass has no `__hash__` and `add()` refuses it. Identity is also the
  right comparison for a detector: two configured the same are not the same detector.
- **A base query needs a condition that binds its variable.** A rule tree whose base query has
  no `where` yields nothing at all, silently. The base condition here is the edge fit's own
  capability, which is load-bearing rather than a tautology: a target with no modelled outline
  is refused with `NoDetectorAnswersTheLook` rather than reported as nothing seen, and that is
  `robokudo-detector`'s gap stated rather than hidden.

#### Deliberately not built, both recorded rather than skipped

- **The history conditions.** The item was widened on 2026-08-31 so the tree reads what has
  lately happened to the target. The believed place is defined once, by
  `pieces-looked-for-where-expected`, which is `not_started` behind #225, so building it here
  would build it twice -- the duplication these notes record three times over. The tree reads a
  situation rather than a bare pair of properties, so those arrive as rules added under it.
- **A measured colour for the board.** The rule that sends an amber piece to the edge fit reads
  the colour the world states, and `BOARD_COLOR` is `Color.BEIGE()`, eleven hues from the wood
  the camera measures -- recorded by #221 already. So on the real board that rule does not fire
  yet; the tests state the colour the renderer actually draws, which is the lid's measured hue
  19, so the rule is exercised against a truthful world. Moving measured colours onto the twin
  is `detector-parameters-from-knowledge`'s ask, and this is a second reader for it.

**Nothing in this workspace states a finish yet**, so on the scenes as they stand every look
still falls to the edge fit. That is the same shape as `surfaces-from-world`'s
`supporting_surface` being `None` on every world, and it is asserted directly by
`test_nothing_is_annotated_yet_so_every_look_falls_to_the_edge_fit` rather than left for a
reader to discover.

#### The environment, which is worse than #223 recorded

`uv sync --extra dev --python 3.12` **does not work any more**, and it is not this branch's
doing: `pyproject.toml`'s `[tool.uv] override-dependencies` uses a map form uv rejects
outright (`invalid type: map, expected a string containing a PEP 508 requirement`), on both
uv 0.8.17 and 0.9.5, and it reproduces on unmodified `main` -- it arrived with `b37c29996`,
"Add alternative package for treon dependency docopt". What works instead is a Python 3.12
virtual environment with every workspace package installed editable and `casadi~=3.7.0` pinned
as `semantic_digital_twin` declares; casadi 3.8 raises `NotImplementedError` out of
`FunctionBuffer_set_res` on any forward-kinematics call.

#### Landing hazard

`LoosePieceDetector` is renamed to `EdgeFitDetector` across the perception package and
`detect` gains two parameters, the shared edges and the candidates it was chosen for. #225
edits `pipeline.py` and will conflict; the resolution is mechanical, the same way #223's
`RectifiedFootprint` rename resolves -- take its edit, spell the class `EdgeFitDetector`, and
hand `detect` the frame's shared edges.

#### A tooling fault found on the way

`.claude/hooks/plan_item_bootstrap.py` writes item fields at four-space indentation
(`ITEM_FIELD_INDENT`) while this plan's `plan.yaml` indents them by two, so both `open` and
`record` produce invalid YAML and fail inside `save-plan.sh`, whose output the script swallows
with `capture_output=True`. It is the same family as #160 and it is unfixed on `main`. Worked
around by editing `plan.yaml` directly; worth its own bug-fix pull request.

#### Correction, 2026-08-31: the EQL-native RDR engine is usable, and this section said it was not

The developer's correction, and it overturns the third bullet above. That bullet read the
`D-core-*` stack's *merge* state as its usability -- "eight unmerged pull requests deep in a
stack whose root (#64) is still open" -- which contradicts this plan's own standing rule, set
out in the budget section: **`depends_on` means stacked on, never waiting for a merge.** By
that rule an open, reviewed, out-of-draft branch is available to build on, and the whole
chain is exactly that:

#64 -> #65 -> #66 -> #67 -> #98 -> #159 (`EQLSingleClassRDR`) -> #210 -> #79 -> #76 -> #80 ->
 #77 (the `@rdr` decorator)

Every one of those is open and out of draft, and none carries `needs-resolution`. (#68 is a
draft, but it is the older parallel branch off `D-core-support` that #159 supersedes, and #81
hangs off it rather than off this chain.) So the accurate statement is: **the classic
`krrood.ripple_down_rules` machinery is unusable, and both the EQL-native rule trees and the
EQL-native RDR engine are available** -- the first on `main`, the second by stacking.

**This does not change what #231 built**, at the developer's decision, and the reasons are
worth keeping because they are about where the engine earns its place rather than about
whether it works:

- `EQLSingleClassRDR.query` is `field(init=False)` -- the RDR *grows* its own tree through
  `fit_case`/`fit` with an `Expert`, and there is no public way to hand it one already built.
  So expressing this item's two rules through it makes them fitted from cases and targets
  rather than stated, which is a different authoring model for the same two rules.
- Merging #159 into #231 would add **9,236 lines** to the diff of a pull request whose own
  change is about 600, and #77 would add **22,745**. That is another plan's work carried
  through this one's review.
- What the engine actually adds -- `fit` with an expert, `render_tree`, the corner-case store,
  the model file and the interactive expert interface -- is what the *next two* items are
  written around, not this one. `detector-parameters-from-knowledge` asks for the contour
  chain to become "an inspectable rule tree", which is `render_tree`; and
  `tune-detection-rules-against-the-camera` is a presenter over the `ConclusionHelper`, which
  is the expert interface. **Both should stack on #159, and the tuning item on #77, rather
  than on a hand-written tree.**

**What this changes for the plan is the schedule, and it changes it twice over.**
`detector-parameters-from-knowledge` was recorded as blocked on the ripple-down rules becoming
usable; it is not blocked, and it now has a named branch to stack on. And
`tune-detection-rules-against-the-camera` was deferred past the deadline partly as tooling
that would have to be built; #76, #80 and #77 are that tooling, already written and reviewed,
so what remains of that item is the perception-side presenter rather than the expert interface
underneath it. Whether that is enough to un-defer it is the developer's call and is not taken
here.

Worth generalizing, because this is the second time this plan has recorded a blocker that was
not one: **"unmerged" is not "unusable" on a plan whose standing rule is to stack.** Read a
dependency's draft state and its review state, not its merge state.

### `pieces-looked-for-where-expected`: what it took, and the source that was measured and not armed

Built 2026-08-31 as pull request #232, `d8b654433`. 21 new tests; `397 passed, 1 skipped,
11 xfailed` across `test/experiments_test/` against `376 passed, 1 skipped, 11 xfailed` on
the parent, which is the 21 added here and nothing else moved.

**Every one of the six captures reports exactly what the parent reported**, compared
detection by detection -- category, surface, position to the millimetre, and agreement --
and `detect` costs **0.344 s per frame against the parent's 0.344 s**, both measured in
this container against the parent in a worktree with its own `*/src` on `PYTHONPATH`, per
what #222 recorded about baselines taken outside the main checkout. So the restructure is
behaviour-preserving on real data and costs nothing.

**The hole source was built, measured twice, and left out at the developer's decision.**
The item's note names three sources and calls the first two enough for the four failing
captures. Sweeping the board's own detected holes was built first, and the first reading of
it was reported in seconds against the node's 0.5 s period: 0.715 s against 0.344 s, so
"0.36 s on top of a 0.5 s frame budget". **That reading was wrong, and the fault it came
from is worth more than the number.** This container's speed moves between runs by more
than the difference being measured -- the shipped branch, unchanged, measures 0.344 s in
one run and 0.229 s in another -- so a second measured here is not a statement about the
robot's frame budget at all. The only figure that survives a re-run is the ratio to a
baseline taken in the same run.

Re-measured that way, with the shipped branch as the same-run baseline and with two
narrowings the first pass had not tried:

| what the lid pass evaluates | cost | lid captures failing | pieces reported that are not there |
| --- | --- | --- | --- |
| colour, and what the world places (shipped) | 1.0x | 4 | 3 |
| and every hole, every piece | 1.7-1.9x | 1 | 20 |
| and every hole, narrowed | 1.3x | 2 | 12 |

*Narrowed* is two economies together: a hole expects only the pieces that fit through its
own measured opening, and believed places whose reaches overlap are merged into one, which
also folds a hole a colour already covers into that colour's hypothesis. Together they take
a third off the cost of arming the holes and neither restores the recall the unnarrowed
sweep reaches -- because the openings they read are the same mislocated hole measurements
`holes-fitted-like-pieces` says are wrong. Narrowing by a hole's *category* fails the same
way and more expensively, losing **7 real pieces**; reading each hole's reach off its own
footprint rather than the seeding distance costs recall too. All three are recorded so none
is tried again.

No configuration regresses the table: `non_inserted_objects` is the only capture whose
table reading is wrong, and it is wrong in the shipped state too, for the reason #225
recorded.

**The developer's decision, taken on the table above, is to leave the hole source out**, so
what ships is the restructure alone. The trade refused is 1.7-1.9x the frame cost and three
false lid reports becoming twenty, in exchange for three of the item's four lid marks.

What the measurement shows either way is that **sweeping every hole for every piece every
frame is a second exhaustive pass, not knowledge-directed search**. What makes a seeded fit
cheap and precise is a belief that names *which* piece at *which* place, and the two things
that can say that are the world (built here) and the object's own history
(`expectations-from-events`). So the pipeline believes on its own from the world, and
anything more particular is supplied by whoever asked for the look -- which is the shape
the request language and that item both need, and which
`test_a_piece_wearing_the_surfaces_own_hue_is_found_where_it_is_expected` exercises end to
end.

**The lid marks therefore stay, and now name `expectations-from-events`.** The item's
premise is right -- the lid failures are a seeding fault, not a parameter fault, and this
branch is what makes them reachable -- but a capture carries no world, so nothing on a
capture believes anything about the lid yet. The ownership move off
`detector-parameters-from-knowledge` stands; the item that clears them is the one that
supplies the belief, not the one that tunes the detector.

**Two smaller calls, both recorded rather than left implicit.**

- A detection is measured by the outline the fit settled on rather than by the colour blob
  it may have come from. That is the piece's own footprint, and it is the only outline a
  hypothesis from anything but a colour has -- so `footprint` keeps one meaning instead of
  two. `WorkspaceRegion.to_pixels` is the inverse of the `to_world_position` that was
  already there, so a fitted outline is measured and its depth read exactly as a segmented
  one is.
- `PieceMatcher` lost `search_radius` and `hue_tolerance`. A reach belongs to the belief
  that states it, and colour belongs to whatever read it -- the matcher fits outlines and
  now knows nothing about either. `SEED_REACH` carries the old radius and its measured
  justification into `hypotheses.py`.

**The believed place is defined here, once**, as "Two items that meet at one type" settled:
a region of a named surface and an interval of yaw. #227, `search-clipped-to-a-predicates-region`
and `expectations-from-events` all read it rather than building their own.

**The environment, since the last three items each recorded a different one.** `uv sync
--extra dev --python 3.12` builds the whole workspace, as #223 recorded -- but the `uv` first
on this container's `PATH` is 0.8.17, which cannot parse this repository's own
`pyproject.toml` (`override-dependencies` in its table form) and fails identically on
unmodified `main`. `/usr/local/bin/uv` is 0.12.7 and works. `docformatter` and `black` are
not in the dependency set and have to be installed before `scripts/format_docstrings.py`
will run.

**Landing hazards.** #223's `Footprint` -> `RectifiedFootprint` rename conflicts with this
branch's edits to `pipeline.py`, `detections.py` and `piece_matcher.py`, the same mechanical
way it does with #205, #221 and #225. And #223 is what makes the ORM walk this package at
all, so it will be the first thing to meet `PieceHypothesis.candidates`, a tuple of
dataclasses; whether ORMatic maps that is worth checking when the two meet, since the full
regeneration does not run in a container.

## `tune-detection-rules-against-the-camera` is un-deferred (2026-08-31)

The developer's decision, taken the same day the RDR correction above was made, and it
follows from it. That item was deferred past the 2026-09-15 deadline as "tooling for
authoring rules rather than a piece of the claim", and the deferral was mostly paying for
tooling that would have to be *built*. It does not: **#76 is the interactive expert
interface, #80 the model-file store and #77 the `@rdr` decorator** - the tip of the same
`D-core-*` stack, all open, out of draft and reviewed. By this plan's standing rule that
`depends_on` means stacked on, never waiting for a merge, all three are available to build
on today.

So the item is `not_started` rather than `deferred`, and it **stacks on #77**, the tip,
rather than on any lower link: the `@rdr` decorator is what makes a rule-concluded value a
normal function call, and #76 and #80 come with it. What remains of the item is only the
perception-side presenter - the live camera beside the parameters a rule would conclude -
rather than the expert interface underneath it, which is what made it look expensive when
it was deferred.

It keeps its dependency on `detector-parameters-from-knowledge`, since that is what gives
it parameters to conclude at all, and that item stacks on #159 in the same stack. Nothing
else changes: `robokudo-detector` stays deferred, and it remains the first thing to drop if
the deadline tightens.

Worth generalizing alongside the correction above, because this is what that correction
*cost*: a blocker recorded as "the tooling would have to be built" outlived the tooling
being built, on a plan whose whole method is to stack on unmerged branches. A deferral is a
claim about the state of the world and needs re-reading when that state moves, exactly like
a blocker does.

### `pieces-looked-for-where-expected`: the review round of 2026-08-31

Two comments, both on `hypotheses.py`, answered in `571042923`. Neither thread was
resolved: each was answered differently in part, and the standing convention is to leave
those for the developer to close.

**A believed place is not a pose, and its centre is a point.** The first comment asked
*"isn't this basically a 2D Pose? or a Point?"*. A pose is one placement; a
`BelievedPlace` is a set of them - a disc of positions (`radius`) and an interval of turns
(`yaw`), which is precisely what makes it something to search rather than something to
look up, and collapsing the two into a `Pose2D` would drop both. The centre is a point,
though, and a pair whose positions carry meaning should be named, so it is `PlanarPoint` -
the type `HoleFootprint.center` and `PolygonMeasurement.centroid` already used, moved with
`PlanarSize` out of `hole_geometry.py` into a new `montessori/planar_geometry.py` and no
longer worded as the board mesh's own plane. `MatchedPiece.center` and
`Orthophoto.contour_center` say the same thing the same way, so nothing converts at a
boundary.

**Not `spatial_types.Point2`, and the reason is measurable.** `Point2` is identity-equal:
`Point2(0.6, 0.2) == Point2(0.6, 0.2)` is `False`. As a field of a frozen value object that
makes two beliefs about the same place compare unequal - silently, in any dedupe and in
every test that compares places. It also carries casadi and a reference frame into a numpy
sweep (22 µs to build one, 35 µs to read a coordinate back). #202 made the same call for
`HoleFootprint` on the frame argument alone; the equality is the stronger half of it. The
sdt spatial type is what a *reported* detection carries, in `MontessoriShapeDetection.pose`.

**A belief now keeps the source itself, not a label for it.** The second comment asked why
`BeliefSource` was a `StrEnum`, and proposed a mixin that the world model, the detectors
and an expert-like asker all inherit, placed in krrood because krrood is the top of the
stack. Done as asked: `krrood/patterns/belief_source.py` holds the abstract mixin,
`World` inherits it in `semantic_digital_twin`, `LoosePieceDetector` inherits it here, and
the third case - asked for - is whoever called for the look passing itself. So
`hypothesis.source is pipeline.world` and `is pipeline.piece_detector` are assertions
rather than enum comparisons, a source can be asked what else it says (the
belief-state-updated-by-successful-actions case), and a new kind of source needs no edit to
anything that reads a belief - Open/Closed, where the enum was a closed set.

**Two things deliberately not done, both recorded on the thread.**
`krrood.ripple_down_rules.experts.Expert` is not reused and not rebased on `BeliefSource`:
it answers questions about a case to grow a rule tree, carrying answer files, a user prompt
and code generation with it, and says nothing about where a thing is - so making it a
belief source would couple the two for a consumer that does not exist. It is a one-line
base addition the day an expert should be able to seed a look. And the mixin declares no
members: nothing that reads a belief needs anything from its source but its identity yet,
and how sure a source is belongs to `expectations-from-events`, where a belief first gets a
spread that is not the seeding default.

**Verification.** 400 passed, 1 skipped, 11 xfailed across `test/experiments_test/` against
397 before the round - three tests added, for a place naming the axes of its centre, a
hypothesis naming the source that suggested it rather than a kind of source, and a
colour-suggested detection naming the detector that read it. One test added in
`semantic_digital_twin`, and `test_worlds/test_world.py`'s failing-and-erroring set is
byte-identical with and without `World`'s new base, checked by name rather than by count.
The sdt ORM interface regenerates and imports with the base in place; `World` is not mapped
as a DAO and neither is `BeliefSource`, so nothing in the interface moves.


### `choose-detection-method`: the review round of 2026-08-31, and what "no point of using EQL" meant

Two threads on #231, answered as `92afdcd82`. The second is a design change and worth
recording, because it is about what a rule tree is *for* rather than about this branch.

The reviewer's words: *"if you are going to create the query/rule tree here and also
evaluate it here then there's no point of using EQL here at all. This can be native python
logic. The point of using EQL RDRs is extensibility with new situations through interaction
with an expert."* — and, on the follow-up, that it applies everywhere in the branch that
does this, which was `PieceDetector.answers` as well as `DetectorRules.detector_for`.

He is right, and the diagnosis is sharper than "it is slow": a tree built inside the method
that evaluates it is not a tree anyone can hold. Nothing outside that method can read it,
nothing can add to it, and its structure is thrown away the moment the answer is returned —
so every property that distinguishes a rule tree from an `if` is unreachable, and the EQL
spelling buys nothing but ceremony.

**What the branch does now.** The tree is stated once, in `DetectorRules.__post_init__`,
over one variable every rule states its conditions over. A look is decided by binding it to
that variable and evaluating the tree already held. That is not a workaround: it is the
rebind krrood itself performs in `GuardCondition.holds_for` (`rdr/guard_condition.py:60`),
which is how the RDR engine asks a stated condition about one case.

Because the tree outlives the looks it decides, it can be grown while it is in use:

```python
rules.add_rule(rules.stated_look.surface_finish == SurfaceFinish.GLOSSY, detector)
```

`add_rule` attaches the new rule with `ConclusionSelector.insert_at` — the live-growth API,
documented for exactly this ("when an RDR inserts a refinement or alternative after
observing a misclassification"). It attaches as an **alternative** beside the exceptions
already stated rather than as a second refinement of the base rule, and that shape was
measured rather than chosen: two refinements at one anchor make the conclusion reachable by
two paths and the same detector comes back twice, while an else-if chain answers once.

The test that holds it is behavioural: a look at a glossy surface answered by the edge fit
before the call is answered by the added detector after it. Mutation-checked by making
`detector_for` rebuild the tree per look, which fails that test and only that test.

**A measured side effect.** Choosing for one surface costs **1.0 ms instead of 4.4 ms** over
the four known pieces on a matte lid, and the module's own test run went from 42.7 s to
7.5 s. Building a tree per look was most of what the choice cost.

**What is still not there, and why it is not this branch's to decide twice.** The half of
the reviewer's sentence about *interaction with an expert* is unanswered: nothing asks
anyone when no rule fires, `detector_for` still raises `NoDetectorAnswersTheLook`, and the
expert interface lives on #98 → #159 → #76 rather than on `main`. Putting the tree behind
`EQLSingleClassRDR` is the developer's call and he made it earlier the same day — the two
stated rules would become fitted-from-examples, and #159 adds 9,236 lines to a 600-line
pull request. So the reply offers to merge #159 in and leaves the thread open rather than
reversing him silently.

Worth generalizing: **"stated once and held" is the property that makes a rule tree a rule
tree**, and it is cheap. A tree that is built where it is read is an `if` with extra steps,
whichever library spells it.

## `holes-fitted-like-pieces`: one layout, three degrees of freedom, and the board's pose falling out of it

Kicked off 2026-09-01 in `auto` mode, as pull request #236 off
`claude/plan-item-kickoff-kdp-o4l189` (#232, open and out of draft, so ready to stack on
-- `check_dependency_readiness.py` reports `open_ready`). It is based on #232's current
tip `bc0a17d2`, not on the `d8b654433` the item's note records. The session's branch
arrived cut from `integration` rather than from #232 -- the hazard #199 exists to refuse,
and the fifth time on this plan after #223, #225, #227 and #232 -- and was re-cut onto
#232's tip before the first commit.

The mechanical scope check reports every path this touches absent from `main` and shared
with #232, #225, #222, #227 and #223, which every round on this plan has already
recorded as expected: every file in this plan is introduced by #202, so path overlap
alone would fold the whole plan into one item. The purpose check is the one that matters
here and it comes back clean: #232 measured the board's holes as a source of hypotheses
and left them out at the developer's decision, recording that the openings it read are
"the same mislocated hole measurements `holes-fitted-like-pieces` says are wrong". So
that item deliberately did not do this, and what remains once its edits are removed is a
rigid layout fit that no earlier item states in any form.

### The evaluator is #232's, and it is extracted rather than written twice

The item's own note says it depends on `pieces-looked-for-where-expected` "because
fitting a known model at a believed pose is exactly the evaluator that item builds, and
two branches independently writing the same evaluator is the duplication the personal
notes already record twice". That is honoured by extraction, not by a second copy:
`PieceMatcher`'s coarse-then-fine placement sweep becomes an `OutlineFitter` over a
`KnownOutline` -- something whose outline is known exactly beforehand and can be laid
over the picture at any placement -- and both `KnownPiece` and the board's hole layout
are one.

`EdgeDistances.agreement` already scores a batch of outlines of shape
``(..., points, 2)``, so a layout of six holes is one outline of about three hundred
points rather than anything new measured. The belief a fit is aimed at is #232's own
`BelievedPlace` -- a stretch of a named surface and an interval of turns -- which is
exactly what a seed from the board detection is.

### The placement *is* the board's pose

`HoleFootprint.center` is in the board mesh's own local frame and `cut_board_mesh` builds
the blank about that origin, so a layout fitted in mesh-local coordinates returns the
board's own pose directly. Six outlines constrain it where `_board_around` had only
`minAreaRect` over however many hole centres happened to be found, which is why the
second expected-to-fail mark below is a consequence of this fit rather than separate work.

### The dark patches stop being classified and become a seed

The board is still *found* the way it is found today -- the largest surface with several
hole-sized dark patches cut through it, clustered to a board-sized group -- because the
layout fit needs somewhere to start. What changes is that those patches are no longer
classified into holes: they supply a centre and a long axis, and the layout fit settles
everything that is reported. `BoardDetector.classifier` goes with them.

`CrossSectionClassifier` and its `FootprintClassifier` base are then used by nothing but
their own tests. `AGENTS.md` says to consult the developer before removing something
used only in tests, so they are left standing and the removal is asked on the pull
request rather than taken here -- the same call `surfaces-from-world` made about the
widest-or-highest face. `piece_matcher.py`'s module docstring, which cites the classifier
as "how the holes in the board's lid are still read", stops being true and is corrected
either way.

### Two expected-to-fail marks, and only one of them is about holes

Both name this item and both are this item's to remove, which the benchmark module's own
docstring states as the contract:

- `test_every_hole_in_the_board_is_found` -- all six holes, with the categories the mesh
  was cut with.
- `test_only_the_pieces_resting_on_the_table_are_detected_there` on
  `non_inserted_objects`, where #225 measured the board reported at -29.7 degrees against
  -7.6 in the other five about the same centre, so the stretch of table it is taken to
  hide is turned with it. That mark comes off only if the fitted pose is actually right,
  which is measured rather than assumed; if it does not, that is a finding to record and
  the mark stays, re-pointed at whatever the measurement says owns it.

### What is deliberately not attempted

- **Deciding a detection by what else could have produced its edges.** A prism template
  reaches 0.85 to 0.89 on the board's middle with no prism there, and no threshold
  separates that from a genuine piece. That is `competing-explanations`, which depends on
  this item precisely because a settled layout is what predicts the edges the board
  itself produces.
- **Arming the holes as a source of piece hypotheses.** #232 built it, measured it twice
  and left it out at the developer's decision; correcting the hole measurements is what
  this item does, and whether that changes the trade is a re-measurement for the item
  that owns the belief, not a re-opening of a decision already taken.

### Verification

Tests first, at three levels, so each failure names its own cause:

- The layout on its own: its outline at a turn is the mesh's own six footprints placed
  rigidly, asserted against `detect_hole_footprints()` rather than a retyped copy of it;
  a layout fitted over edges drawn at a known placement recovers that placement.
- The pipeline over the rendered scene: every hole is reported, at the renderer's own
  placed centres, with the model's categories rather than a classifier's guess.
- The captures, which is the measurement that matters: the two marks above, and no
  regression of `test_every_piece_resting_on_the_table_is_found` or of the other five
  captures' table readings.

Cost is measured as a ratio to a same-run baseline, never in seconds against the 0.5 s
period -- what #232 recorded about this container's speed moving between runs by more
than the difference being measured. The lid plane's edges are read once per frame by the
board detector, which is a second `EdgeDistances.of` on a plane the piece passes do not
share; #231's `RectifiedFrame` is what removes that duplication and is not on this
branch's stack, so the cost is reported rather than designed around.

Run under the environment #232 recorded: `/usr/local/bin/uv` (0.12.7), since the `uv`
first on this container's `PATH` cannot parse this repository's `pyproject.toml`.

### Landing hazards

#223's `Footprint` -> `RectifiedFootprint` rename conflicts with this branch's edits to
`pipeline.py` and `detections.py`, the same mechanical way it does with #205, #221, #225
and #232. #231 renames `LoosePieceDetector` to `EdgeFitDetector` and hands the detectors
a frame's shared edges; a board detector that reads its own lid-plane edges is the next
thing that wants that mechanism, which is worth knowing when the two meet.

### The bootstrap script's indentation fault is unfixed, and it is the same one #231 hit

`.claude/hooks/plan_item_bootstrap.py` still writes newly-added item fields at four-space
indentation while this plan's `plan.yaml` indents them by two, so `open` produced invalid
YAML and `save-plan.sh` refused it -- with the error swallowed by `capture_output=True`,
exactly as #231 recorded on 2026-08-31. Worked around again by editing `plan.yaml`
directly. It is the same family as #160 and still wants its own bug-fix pull request.

## `search-clipped-to-a-predicates-region`: two parents that had to meet, and where a clip's extent comes from

Kicked off 2026-09-01 in `auto` mode, as pull request #238 off
`claude/plan-item-kickoff-perception-ogf2g9` (#227). Both dependencies are open and out
of draft, so `check_dependency_readiness.py` reports `open_ready` for each. The session's
branch arrived cut from `integration` rather than from anything this plan is stacked on
-- the hazard #199 exists to refuse, and the sixth time on this plan after #223, #225,
#227, #232 and #236 -- and was re-cut onto #227's tip before the first commit.

### This is the first item on the plan whose two parents are on different stacks

Every earlier item took one parent and stacked on it. This one cannot: its two
dependencies diverge at #221 and neither contains the other.

```
#202 -> #205 -> #221 -> #222 -> #227   the backend, and reading a statement's predicates
                     \-> #225 -> #232   occupancy, and the believed place
```

`backend.py`, `scene_request.py` and krrood's `LookRequest` exist only on the first line;
`hypotheses.py` and `occupancy.py` only on the second. This item needs both, so #232 is
merged in rather than waited on, which is this plan's standing `depends_on` rule and the
same move #227 made with #229.

**The merge is two files and both resolve as a union**, measured before the branch was
opened rather than assumed: `pipeline.py`, where #222 added a request parameter to
`searched_surfaces`/`detect` and #232 rewrote the same `detect` around hypotheses and the
occupancy pass; and `test_montessori_perception.py`, where #232's side still carried the
four `PerceivedObjects` tests #222 retired when the backend replaced them, so the
resolution takes #232's new tests without that section.

Worth knowing for `expectations-from-events` and `competing-explanations`, which both
depend across the same divide: whichever of them runs first pays this merge, and it gets
no cheaper while the two stacks grow.

### What the item is, in one line

#227 narrows a look by a relation the world means rather than by an attribute spelled as
a string, but the narrowing it buys is *which pass runs*, never *how much picture that
pass reads*: `rectify` projects every plane over the whole searched patch of table
whatever the statement asked about. This is where narrowing stops being a filter over
what a detector returned and becomes less picture to search in the first place -- the
developer's second mechanism on r3893602153, deferred out of #227 rather than dropped.

### Where a clip's extent comes from, which is not simply the world

The item's own ask names two routes, and measuring the plan's own record settles them
differently:

- **A predicate that names a region outright.** `InsideRegion(body, region)` carries a
  `Region` -- a world entity with a pose and an `area` -- so its extent is read directly
  and is the world's answer.
- **The supporting-surface predicate.** `SupportedBy(piece, board_lid)` names a body
  whose surface extent `WorkspaceSurface.of` already reads, from the declared
  `supporting_surface` region or the body's own widest horizontal face. This is the half
  the ask asked to check, and the answer is *yes for the table and no for the lid*.

The reason is already on this roadmap. Under *"Finding the surface by looking"* the
world's board pose is recorded as having drifted from the real one, which is why #221
took the lid's **height** from the world and its **extent** from the detection, and why
#225 used the *detected* board rather than the modelled one for what the board hides.
Clipping the lid pass to the world's declared lid region would reintroduce exactly the
constant that split removed. So a clip's source follows the same split: the table's
extent from the world, which does not move; the lid's from the board detection of that
very frame, grown by enough for a piece standing at the lid's edge still to fit in the
picture -- a margin read off `KNOWN_PIECES` rather than chosen.

### What is planned

- `WorkspaceRegion` gains intersection and a margin, so two narrowings compose rather
  than the last one winning.
- `SceneRequest` gains the stretch of plane a look may search, filled by
  `MontessoriPerceptionBackend` from the statement's predicates through
  `LookRequest.related_by` -- the reader #227 built -- for `SupportedBy` and
  `InsideRegion` alike.
- `MontessoriPerceptionPipeline.rectify` takes its region from the search rather than
  always the table's, and `searched_surfaces` resolves each pass's own region.

**The invariant #222 states is kept**: a narrowing is an economy, never what makes an
answer right. Every clip is a subset of what the statement already asserted, and
`relations_hold` re-checks over what came back.

### Seeing each condition, and why the viewer is a script and not a test

The developer asked for the constraints to be visible one at a time, and for the viewing
half not to be a test. Two pieces:

- **`watch_narrowing.py`**, beside the existing `watch_captures.py` and
  `watch_camera.py`, drawing the picture after each condition is added and holding each
  step until a key is pressed. Each window is labelled with the statement so far,
  verbalized through `verbalize_expression` with the perception backend -- so the label
  reads *"Look for ..."* off the `Directive.LOOK_FOR` #222 added rather than off a
  hand-written caption, which is the paper's own distinction between recalling and going
  to look.
- **A test with no window at all**, so it runs in CI. `ImageDisplay` is already an
  abstract base with `OpenCvDisplay` as its one implementation, so a recording display
  makes the step sequence, its labels and its regions assertable headlessly. That is the
  existing seam being used rather than a new one cut for the test.

### Verification

Tests first, at three levels, so each failure names its own cause: the region arithmetic
on its own; the backend reading each predicate into a region; and the pipeline over the
rendered scene and then the captures, where the measurement that matters is that a
clipped look reports the same detections an unclipped one does for the surface asked
about, and costs measurably less. Cost as a ratio to a same-run baseline, never in
seconds, per what #232 recorded about this container's speed moving between runs by more
than the difference being measured.

### Landing hazards

#223's `Footprint` -> `RectifiedFootprint` rename conflicts with this branch's edits to
`pipeline.py` and `orthophoto.py`, the same mechanical way it does with #205, #221, #225,
#232 and #236. #231 renames `LoosePieceDetector` to `EdgeFitDetector` and adds
`RectifiedFrame`, which rectifies each plane and reads its edges once per frame; it is a
sibling off #222, and a per-surface search region is the next thing that wants that
mechanism, since a region that differs per pass is what makes a shared rectification
non-trivial. #236 sits on #232 and edits `pipeline.py` too.

### The bootstrap script's indentation fault is still unfixed

`.claude/hooks/plan_item_bootstrap.py` writes item fields at four-space indentation while
this plan's `plan.yaml` indents them by two, so `open` fails inside `save-plan.sh` with
the error swallowed by `capture_output=True` -- exactly as #231 recorded on 2026-08-31 and
#236 again on 2026-09-01. Worked around a third time by editing `plan.yaml` directly. It
is the same family as #160 and still wants its own bug-fix pull request.

### `search-clipped-to-a-predicates-region`: what it took, and the clip that was a different picture

Built 2026-09-01 as pull request #238. 23 new tests; `437 passed, 1 skipped, 11 xfailed`
across `test/experiments_test/` against `414 passed` on the merge of its two parents,
which is the 23 added here and nothing else moved.

#### A clip that moves the sampling grid is not a clip

**The one finding worth more than the feature.** A rectified pixel samples the world
point its patch's own lower corner puts it over, so a crop whose corner falls between the
samples of the patch it came from rectifies *every* point half a pixel away from where
the uncropped pass had it. That is not less of the same picture; it is a different one.

It showed up as a regression the first run caught: on `tracy_pickup_demo` the lid pass
reported a second cylinder where the shipped branch reported a cube. What gave the cause
away was that it was **not monotonic in the size of the crop** -- 0 mm and 100 mm of
overhang kept the cube, 21 mm and 45 mm lost it -- which no amount of "the crop is too
tight" explains.

| overhang | unaligned | on the surface's own grid |
| --- | --- | --- |
| 0 mm | cube 0.716, cylinder 0.662 | cube 0.664, cylinder 0.673 |
| 21 mm | cylinder 0.728, cylinder 0.659 | cube 0.664, cylinder 0.673 |
| 45 mm | cylinder 0.728, cylinder 0.659 | cube 0.664, cylinder 0.673 |
| 100 mm | cube 0.716, cylinder 0.662 | cube 0.664, cylinder 0.673 |

The right-hand column is what the *unclipped* pass reports for those two pieces,
agreement for agreement. So `WorkspaceRegion.intersection` answers on its receiver's own
grid -- the shared ground taken out to the nearest sample, never in -- and every call
site is arranged so the receiver is the on-lattice one. The cube and the cylinder scoring
within 0.012 of each other at that seed is what made a half-pixel shift visible at all,
and that fragility is `competing-explanations`' to fix rather than this item's.

Worth generalizing beyond this item: **anything that re-frames a rectification has to
land on the same lattice**, and the cheap way to find out that it does not is to vary the
crop and check the answer is flat rather than merely plausible.

#### What the clip costs, and what it is worth

Measured over all six captures in one run, against the same pipeline with the clip taken
out, so the columns are comparable:

| what the statement says | unclipped | clipped |
| --- | --- | --- |
| nothing | 0.273 s/frame | 0.207 s/frame |
| supported by the lid | 0.118 s/frame | 0.056 s/frame |

Same 20 and 6 pieces in every column. So the clip halves what #222's supporting-surface
narrowing already bought, and a look that states the surface costs a fifth of one that
states nothing and is unclipped. It helps a look that states nothing too, because the lid
pass is clipped to the board either way.

It is also a precision win the item did not ask for: on that capture the lid pass reports
6 detections unclipped, three of them the ghost prisms `competing-explanations` owns, and
2 clipped. Nothing was tuned to get that -- the ghosts simply lie outside the board.

#### Where the extent comes from, as the plan predicted

The kickoff section above called the split -- the table's extent from the world, the
lid's from the detection -- and building it bore it out. `SurfaceSearch` answers it from
what it already carried: `boundary` is the lid as it was *seen*, which is exactly the
extent the drift makes the world unable to state, and the overhang is
`LARGEST_PIECE_RADIUS`, read off `KNOWN_PIECES` rather than chosen.

#### The board is looked for across everything the statement allows

A look narrowed to the lid still has to find the board, because where the board stands is
what the lid's own extent is read from. So the board pass is clipped by a stated region
but never by a stated surface, and one of the three rectifications a frame costs is not
narrowed by support at all. That is recorded rather than designed around: clipping it to
the world's declared board region is precisely the constant this plan removed.

#### Two things the build needed that the plan had not

- **`recorded_setup` gained the world its own surfaces describe.** A relation is stated
  between entities, and a recording carries no world to name any, so a statement about a
  capture had nothing to be written over -- and a detached `Region` cannot even report
  its own bounding box, since `transform_to_origin` reads the world off its frame. The
  two bodies carry the very names `table_surface` and `lid_surface` record, so
  `WorkspaceSurface.of_body` measures them back to what those functions state.
- **A source says what frame it reports its detections in.** A backend that declares a
  relation as narrowing promises to check it over its own answer, and a region can only
  be read in metres against the frame the things it is stated about are placed in. So
  `MontessoriSceneSource` answers that frame, and `relations_hold` raises
  `LookHasNoReferenceFrame` rather than quietly not checking.

#### #229's tip was merged in for four sentences

#227 took #229 in before it fixed the wordings a `Triple` derives from a class name that
is not verb-first, so a support relation stated here verbalized as *"it supports by a
specific Body"*. The demonstration names its windows by how the statement reads, so an
ungrammatical clause is not cosmetic here. Merged rather than waited on, per this plan's
standing rule; `predicates.py` is byte-identical to #229's tip afterwards, and its one
failing test and thirteen collection errors reproduce on #229's own branch.

#### Seeing each condition, and why the viewer is a script

`watch_narrowing.py` draws the picture left after each condition and holds it until a key
is pressed, naming every window by how the statement reads so far -- through
`verbalize_expression` with the perception backend, so it opens with the
`Directive.LOOK_FOR` #222 added rather than a caption somebody wrote. On
`tracy_pickup_demo`: 0.635 m2, then 0.061, then 0.024.

`ImageDisplay` was already an abstract base with `OpenCvDisplay` as its one
implementation, so the test drives the same run through a display that records what it
was handed. The step sequence, the window names and the sizes of the pictures are checked
in CI with no screen, and no test opens a window.

#### The environment, which is worse again than #232 recorded

#232 recorded `/usr/local/bin/uv` (0.12.7) as the way round this repository's
`pyproject.toml` defeating uv 0.8.17. **There is no such binary in this container**, and
the `uv` on `PATH` is 0.8.17, which fails identically on unmodified `main`. Installing uv
0.12.8 from `astral.sh` into a scratch directory builds the whole workspace. Worth
recording as the third different environment three consecutive items have found.

#### Landing hazard worth more than the mechanical ones

#231's `RectifiedFrame` rectifies each plane and reads its edges once per frame, however
many detectors ask for them. A region that now differs per pass is what makes that
sharing non-trivial: two detectors asking for the same plane may no longer be asking for
the same picture, so what is shared has to be keyed by the region as well as by the
height. #223's `Footprint` rename conflicts the usual mechanical way, and #236 edits
`pipeline.py` too.

## `detector-parameters-from-knowledge`: the numbers as knowledge, and the engine this item was written around

Kicked off 2026-09-01 in `auto` mode, as pull request #239 off
`claude/choose-detection-method-gf64yp` (#231, open and out of draft, so ready to stack
on -- `check_dependency_readiness.py` reports `open_ready`). The session's branch arrived
cut from `integration` rather than from anything this plan is stacked on -- the hazard
#199 exists to refuse, and the seventh time on this plan after #223, #225, #227, #232,
#236 and #238 -- and was re-cut onto #231's tip before the first commit.

The mechanical scope check reports every path this touches absent from `main` and shared
with #231, #232, #236, #238 and #223, which every round on this plan has already recorded
as expected: every file in this plan is introduced by #202, so path overlap alone would
fold the whole plan into one item. The purpose check is the one that decides it and it
comes back clean twice over: #231 recorded "moving measured colours onto the twin is
`detector-parameters-from-knowledge`'s ask, and this is a second reader for it", and
deliberately did not do it; #221 recorded the same about the board's surface. What remains
once #231's edits are removed is knowledge moving onto the twin's objects and a rule tree
concluding a detector's *numbers* rather than its *identity*, which no earlier item states
in any form.

### #159 is merged in, which is what this item was told to stack on

The item's own note and the correction of 2026-08-31 both say it: this item asks for "an
inspectable rule tree rather than a hand-written condition", and `render_tree` is what
that names. #231 stayed off the engine at the developer's decision and recorded why that
decision does not carry here -- "what the engine actually adds -- `fit` with an expert,
`render_tree`, the corner-case store, the model file and the interactive expert interface
-- is what the *next two* items are written around, not this one. **Both should stack on
#159**, and the tuning item on #77."

Measured before the branch was opened rather than assumed: `D-core-single-class` merges
into #231's tip with no conflict at all, and adds 9,236 lines over 50 files. That is the
figure #231 refused for a 600-line pull request, and it is accepted here because it is the
mechanism this item's own ask names rather than another plan's work carried through this
one's review.

**`EQLSingleClassRDR.query` is `field(init=False)`, so the rules are authored by fitting.**
#231 read that as a cost -- two known rules becoming fitted-from-examples. For this item it
is the right authoring model rather than a concession: the parameters genuinely are
concluded from situations, and `tune-detection-rules-against-the-camera`, which depends on
this item, is a presenter over the expert's `ConclusionHelper` -- the same expert-driven
path. Fitting through a scripted expert here is what that item extends.

### What is built

- **`DetectionParameters`** -- the numbers one look needs, in one value object: the
  saturation and brightness floors a pixel must clear, the area range a piece's outline
  may cover, how tall a piece stands, how far a measured hue may sit from a piece's own,
  the agreement a fitted outline must reach, and how finely the fit steps and turns. The
  detectors read one per look instead of carrying their own defaults, which is the whole
  of the developer's "these are properties of the objects, not of the detector".
- **The knowledge moves onto the twin.** The board's *measured* surface colour replaces
  `Color.BEIGE()`; `ShapeSortingBoard` carries its own hole count, lid area and footprint;
  `ShapeSortingHole` carries the marker thickness; each Montessori shape annotation
  carries the hue and height measured off the real piece.
- **`DetectionParameterRules`** -- an `EQLSingleClassRDR` over the same `TargetOnSurface`
  situation #231's tree already reads, concluding a `DetectionParameters`, authored by
  fitting known situations through a scripted expert and rendered by `render_tree`.
- **The contour accept/reject chain becomes rules.** `EdgeFitDetector._piece_at`'s guard
  chain -- too small or too large, not wholly within the region, standing where another
  surface reaches -- is the chain of ifs the developer named at `pipeline.py:619`. It
  becomes a rule tree that says *which* condition refused a contour rather than returning
  `None`.

### The checkable outcome

#221 and #231 both recorded the same consequence of this item, and it is what makes the
claim measurable rather than structural: `BOARD_COLOR` is eleven hues from the wood the
camera measures, so #231's rule sending an amber piece to the edge fit does not fire on
the real board. With the measured colour on the twin it does. That is asserted, not
observed.

### Deliberately not built here, each recorded rather than dropped

- **The reach of a seeded search.** The 2026-08-31 widening asks for the numbers that say
  *how far* around a believed place to look. #232 already moved that onto the belief --
  `PieceMatcher` lost `search_radius`, and `SEED_REACH` carries it into `hypotheses.py` --
  so concluding it here would build it a second time on a stack that cannot see it, which
  is the duplication these notes record four times over. The stepping and turning numbers
  *are* still the detector's on both stacks, so those are concluded here.
- **How much better one explanation must be than the next.** That is
  `competing-explanations`, which is what `minimum_agreement` cannot be tuned into.
- **The mesh classification thresholds** in `hole_geometry.py`. #236 removes
  `CrossSectionClassifier` outright and takes each hole's identity from the fitted layout
  instead, so concluding those four numbers here would parameterise something that item
  deletes. The developer's own answer on that thread was that they read as the detector's
  rather than the objects' anyway.
- **The interactive presenter**, which is `tune-detection-rules-against-the-camera`.

### Landing hazards

#223's `Footprint` -> `RectifiedFootprint` rename conflicts with this branch's edits to
`pipeline.py` and `piece_matcher.py`, the same mechanical way it does with #205, #221,
#225, #232, #236 and #238. #232, #236 and #238 all edit `pipeline.py` on the other stack
and none of them carries `DetectionParameters`, so whichever of them meets this branch
first pays for threading the parameters through `detect`.

### The bootstrap script's indentation fault is still unfixed

`.claude/hooks/plan_item_bootstrap.py` writes item fields at four-space indentation while
this plan's `plan.yaml` indents them by two, so `open` failed inside `save-plan.sh` with
the error swallowed by `capture_output=True` -- exactly as #231 recorded on 2026-08-31 and
#236 and #238 on 2026-09-01. Worked around a fourth time by editing `plan.yaml` directly.
It is the same family as #160 and still wants its own bug-fix pull request.

### `detector-parameters-from-knowledge`: the knowledge half, and the figure that was wrong

Built 2026-09-01 as `3a493be9` on #239. 7 new tests; `397 passed, 1 skipped, 16 xfailed`
across `test/experiments_test/` against `390 passed, 1 skipped, 16 xfailed` on the
merge of #231 and #159, which is the seven added here and nothing else moved.

**The finish was the gate, not the colour, and the recorded figure for the colour is
wrong.** #221 and #231 both record that `BOARD_COLOR` is `Color.BEIGE()`, "eleven hues
from the wood the camera measures", and #231 concludes from it that its amber-piece rule
"does not fire on the real board until `detector-parameters-from-knowledge` moves
measured colours onto the twin". Measured before anything was changed: `Color.BEIGE()`
reads as hue **17** against the wood's measured **19**. Two hues, not eleven -- and two
is inside the four-hue tolerance either way, so that rule was already falling back to
the edge fit and the colour move does not change its answer.

What actually kept #231's tree from ever firing on a real world is the other thing that
item recorded: **nothing in this workspace states a finish**, so the matte rule could
never hold whatever the colours were. So the checkable outcome this item delivers is the
finish, and the colour comes with it because it is the same move: the board's lid states
the hue measured off the real board and `SurfaceFinish.MATTE`, and Tracy's table states
its own near-colourless grey and the `SurfaceFinish.MIRROR` its brushed steel has. Three
tests assert the tree choosing from surfaces read off a built `MontessoriWorld` -- a cyan
cube on the lid answered by the colour blob, a piece on the table by the edge fit, and an
amber prism on the lid falling back to the edge fit because it wears the wood's own hue.

**The table had been drawn in the board's own wood**, which is the same fault `_SHAPE_COLORS`
was fixed for on #202: a nominal colour standing in for a measured one. It has its own
now, and the robot stand with it.

**An appearance has to be stated on the collision geometry.** `WorkspaceSurface.of_body`
picks the widest horizontal *collision* shape and reads the finish and colour off that
one shape -- which is #216's own recorded design ("the fallback ... is the one where the
finish is read off the very shape whose scale and origin that item already reads"). The
board's collision is a hand-built grid of boxes, so a finish stated only on its visual
mesh is one perception never sees. Found by the test failing rather than by reading, and
worth generalizing: **on this codebase an appearance is knowledge only if the collision
geometry carries it.**

#### What is still to build on this branch

The knowledge half landed; the rule tree that concludes the numbers did not, and neither
did the two pieces after it. Recorded here rather than left to the diff:

- **`DetectionParameters`** -- the numbers one look reads the picture with, in one value
  object the detectors are handed rather than carrying as their own fields. This is the
  literal ask in seven of the nine #202 threads, and it is what the rule tree concludes.
  It moves `SurfaceColors`, `SizeRange` and both `PieceDetector`s' `colors` / `piece_size`
  / `piece_height` fields.
- **`DetectionParameterRules`** -- an `EQLSingleClassRDR` over #231's `TargetOnSurface`,
  concluding a `DetectionParameters`, rendered by `render_tree`. The engine's `query` is
  `field(init=False)`, so the rules are authored by fitting known situations *with*
  targets, which asks the expert for `AnswerName.CONDITIONS` only -- a scripted
  `ExpertInterface` writing the condition into the namespace is what that needs.
- **The contour chain as rules** -- `EdgeFitDetector._piece_at`'s guard chain, the
  `pipeline.py:619` ask, saying which condition refused a contour rather than returning
  `None`.

One measurement to carry into the first of those: **every `KNOWN_PIECE` stands 0.03 m**,
so moving `piece_height` off the detector onto the candidates it was chosen for is
behaviour-identical on this set, and provably so rather than by assertion.

#### The environment, which is different again

#238 recorded that `/usr/local/bin/uv` does not exist in its container and that uv 0.12.8
from `astral.sh` builds the workspace. The same holds here -- the `uv` on `PATH` is 0.8.17
and fails on this repository's own `pyproject.toml`, identically on unmodified `main`.
That is the fourth different environment four consecutive items have found. `black` and
`docformatter` are not in the dependency set, and `scripts/format_docstrings.py` shells
out to them by name, so `.venv/bin` has to be on `PATH` and not merely be the interpreter.

### `holes-fitted-like-pieces`: the law the observations broke, and the size that mends it

Built 2026-09-01 as `172c10209` on #236. 17 new tests; `423 passed, 1 skipped, 5 xfailed`
across `test/experiments_test/` against `400 passed, 1 skipped, 11 xfailed` on the parent
-- the 11 layout tests, the 6 scale tests, seven marks off and one on, and nothing else
moved.

**The layout fit is what the item asked for, and on its own it did not work.** Laid over
the real captures it settled at (0.755, 0.107) where the board stands at (0.806, 0.10),
having slid one hole-column; two captures landed a half turn out; and the agreement
landscape across the lid was flat at about 0.3, so which peak won was arbitrary. Drawn
onto the picture the fitted outlines sat over the drawer fronts beside the openings.

#### The mesh is not cut to the board these captures hold

Four of the five dark patches the detector finds are unambiguously real holes, and they
match the mesh's four corresponding hole centres as a **similarity of scale 0.854 with a
2.1-2.6 mm residual**; forced to scale 1 the residual is 5 to 10 mm. Individual holes are
smaller in the same proportion -- 40x40 seen as 32x38, 5x48 as 3x43, 36x42 as 27x36,
22x42 as 17x38.

**No rectification plane accounts for it**, which is what makes this a fact about the
board rather than about the look. Sweeping the plane from 0.90 to 0.97 moves the ratio
only from 0.86 to 0.80, monotonically the wrong way, and closing the gap would need the
holes about 150 mm below the assumed lid -- below the 0.88 table the board stands on.
Recorded so the plane is not swept again.

#### A law, and the hypothesis that makes it hold

The developer's direction, and it is the shape of the fix: where the holes lie relative to
one another is cut into the board and cannot vary, so a look no placement of the layout
reaches is evidence that the board is not the size the mesh was drawn at. The size is then
the hypothesis that restores the law, and **it is persisted rather than re-derived every
run** -- his words, "recorded somewhere such that it becomes persisted knowledge".

`BoardDetector.measure_scale` is that measurement: it tries the sizes such a board could
be and keeps the one whose holes land on the openings actually seen, scoring by the middle
distance from an opening to the nearest hole rather than by edge agreement, which is far
better conditioned. Across the six captures the median gap falls from 19 mm at the mesh's
own size to 3.5 mm at 0.84, and the per-capture answers are 0.82, 0.84, 0.86, 0.87, 0.90
and 0.92.

Their middle, **0.865**, is `recorded_setup.BOARD_SCALE_AGAINST_THE_MESH`. It sits beside
the surfaces the recordings were taken over rather than on the detector, because it is
knowledge about a particular board and not about how a board is looked for: a scene built
from the mesh is the mesh's own size and reads one, which is why all 29 rendered-scene
tests pass untouched. `test_the_board_is_smaller_than_the_mesh_that_models_it` runs the
measurement against each capture, so the number stays answerable rather than only
asserted.

Worth generalizing: **a model that cannot be fitted is a measurement of the model.** The
first three hours of this item went into tuning a fit that could not converge, because the
premise that the mesh gives the outlines "exactly" was read as beyond question. What
settled it was drawing the fit onto the picture and looking at it.

#### What it delivers, and the one thing it costs

The board is found at **(0.805-0.806, 0.10) within a degree and a half of straight in all
six captures**, against the parent's (0.791..0.804, 0.128..0.145) at -5.6 to -29.7 degrees;
all six holes are reported, each verified darker than the board around it, where the parent
found four or five and called most of them triangular prisms.

`test_every_hole_in_the_board_is_found` needed that second half or it would have stopped
measuring anything: a detector that reads its holes off a model reports the model's
categories wherever it puts them, so counting them says only that a board was found. Its
strict mark and `non_inserted_objects`' table-ghost mark are this item's to remove and both
come off.

**One mark goes on**, and it is a real regression this branch surfaced rather than caused.
In `tracy_pickup_demo` a triangular prism laid over the round hole's own rim follows those
edges at 0.682 against 0.673 for the cylinder sitting in that hole; the two claim one
place, so the stronger is kept and the real piece is dropped. The ghost is found on the
table pass before this change too, where a board read as standing forty millimetres from
where it does happened to hide it. Nine parts in a thousand is not a difference any
threshold can be set against, which is exactly `competing-explanations`' claim, so the mark
names that item. Piece accuracy is otherwise unchanged: 7 missed and 4 reported that are
not there, on both sides.

#### The evaluator was extracted, and it is bit-identical

`PieceMatcher`'s coarse-then-fine sweep is now `OutlineFitter` over a `KnownOutline`, which
both `KnownPiece` and `BoardHoleLayout` are, and `points_along` moved to
`planar_geometry.py` beside it. On a fixed input the extracted matcher returns the same
piece, centre and agreement to six decimals as the parent's, which is what says the
extraction is a move rather than a rewrite. Every difference the captures show downstream
of it comes from the board's pose, not from the fit.

Two things the layout needed that a piece does not. It is turned at **half a degree**
where a piece is content with two: half a degree moves the outermost hole of a layout
spanning 180 mm by under a millimetre, and two degrees would move it by three -- further
than the fit's own reach, which is why the first version stalled at 0.75 agreement on
synthetic edges it should have fitted perfectly. And its coarse pass compares at a third of
the points, since six outlines are hundreds of them.

#### What it costs, and where the cost is

`detect` runs at **0.560 s per frame against the parent's 0.370 s** in the same run, which
is over the node's 0.5 s period. Almost all of it is that a board can be stood any way
round, so the turn must be searched over a whole circle.

The fit is therefore searched twice over -- once roughly over every turn, once carefully
around the answer. That reproduces the full search's placement **to the millimetre and the
half degree in all six captures** at a third of its cost; sweeping the circle at the second
pass's resolution costs 0.91 s and answers the same. Coarsening the position grid instead
was tried and is not the saving: 6 mm breaks `non_inserted_objects` and 8 mm breaks five of
six, for 0.2 s.

Two ways to recover what remains, neither this item's: #231's `RectifiedFrame` would share
the lid plane's edges, which this branch reads a second time; and a board that was found
last frame is a believed place, which is #232's own mechanism and would replace the circle
with a few degrees.

#### Deliberately left standing

`CrossSectionClassifier` and its `FootprintClassifier` base are now used by nothing but
their own tests. `AGENTS.md` says to consult the developer before removing something used
only in tests, so they are left and the removal is asked on the pull request -- the same
call `surfaces-from-world` made about the widest-or-highest face.

#### The environment, and the bootstrap fault again

`uv sync --extra dev --python 3.12` works, but the `uv` on this container's `PATH` is
0.8.17 and cannot parse this repository's `pyproject.toml`; `pip install -U uv` puts 0.12.8
at `/usr/local/bin/uv`, which can. `docformatter` and `black` must be installed and the
virtual environment's `bin` put on `PATH` before `scripts/format_docstrings.py` will run,
and the formatter eats the space in ``:param points: ``(n, 2)``` -- worth a look after
running it.

`.claude/hooks/plan_item_bootstrap.py` still writes newly-added item fields at four-space
indentation while this plan's `plan.yaml` indents them by two, so `open` produced invalid
YAML and `save-plan.sh` refused it, with the error swallowed by `capture_output=True` --
exactly as #231 recorded on 2026-08-31 and #236 again here. Worked around by editing
`plan.yaml` directly. It is the same family as #160 and still wants its own bug-fix pull
request.

### `search-clipped-to-a-predicates-region`: every relation that says where a thing may be

Widened 2026-09-01 at the developer's ask, from the two relations #227 could read -- support and
containment -- to the whole family, plus a colour. The ask, in his words: *"I want even more
spatial predicates like right of the square hole, between the square hole and the triangle hole,
in front of the circular hole, at a region around a pose with a certain radius or extents"*, with
the demonstration stating one of them and then filtering by the cube's colour.

#### One abstraction, and it is where the narrowing was always going

`PlacementRelation`, in `semantic_digital_twin.reasoning.predicates`: a relation that says where
the thing it is asserted about may be, and therefore answers two questions rather than one.

- `allowed_space` -- the stretch of the world it leaves, unbounded along every axis it does not
  constrain. This is what a search reads, before anything has been found in it.
- `allows(place)` -- whether one place satisfies it, answered exactly (a signed distance, a
  distance, a projection onto a line), never from the box.

The box is a narrowing and the exact answer is the check, which is the same split the plan already
made between what a search is told and what is re-checked over what came back. A direction running
across the world's own axes leaves the box unbounded rather than reporting a stretch that omits
somewhere the relation allows -- the narrowing gives up, the answer does not.

**A relation stated about nothing is the constraint alone.** That is what let the family have an
`allowed_space` at all: a search has no subject to build the relation about, so every placement
relation declares the thing it is about optional and raises `RelationStatedAboutNothing` rather
than guessing when asked whether it holds without one. It is also what `StatedRelation.constraint()`
builds.

#### What the six directional relations lost, and what they gained

They were six copies of one `__call__` differing in an axis index and a comparison. They are now
the axis and the side, as class variables, over one implementation:

```python
class RightOf(ViewDependentSpatialRelation):
    axis: ClassVar[SpatialVariables] = SpatialVariables.y
    positive_side: ClassVar[bool] = False
```

Two docstrings said the opposite of what the code does (`LeftOf` is +Y, not -Y) and now match it;
`InFrontOf` was also setting a `result` field the other five spell `spatial_relation_result`.
Both operands take entities as well as points, since a statement relates the things the world
holds rather than coordinates measured beforehand. `Between` and `Near` are new, and so is
`Colored`, which is not a placement but is narrowed the same way.

**`Between`'s sideways tolerance is a judgement, so it is stated**, following what #229 recorded
about `minimum_contained_fraction`: half the distance between the two things, to either side, so
what counts as between two things is as wide across as they are far apart. It is a fraction rather
than a distance because how wide *between* reads is set by the two things themselves.

**`Near`'s radius has no default at all** (`field(kw_only=True)`), because how near is near is the
caller's to say. Extents around a pose are `InsideRegion`'s job, which already carries a region
with a pose and a size -- no second predicate for it.

#### krrood: a relation is asserted about one subject

`StatedRelation` read a relation down to *the one thing a triple names second*, which is enough for
`SupportedBy` and nothing else: a direction also needs its point of view, and *between* has two
objects and so is not a triple at all. So `Relation` is now a predicate asserted about one subject
and `Triple` is the two-operand case, `StatedRelation` carries every operand the statement holds
concrete, and `constraint()` rebuilds the relation with nothing standing where the thing sought
would. `narrowing_relations` names the family rather than its members, so the vocabulary grows
without the backend being edited for each new way of saying where something is.

#### Two faults the widening found, and the second is the more interesting

**A stated stretch says where the *thing* is, not which pixels may be read.** Taken literally, the
clip lost a cube standing 25 mm inside the stretch a statement allowed: its rectified silhouette
crossed the boundary, so the colour pass discarded it as only partly seen. The picture now reaches
an overhang past a stated stretch for exactly the reason it already did past a surface's own
boundary, and by the same `LARGEST_PIECE_RADIUS`. A stretch a third the width of the piece standing
in it now finds that piece, measured exactly as the unnarrowed look measured it. **This was a fault
in the clip as first built, not in the new relations** -- `InsideRegion` had it too, and no test
had a piece near enough to a stated edge to catch it.

**The board is what says how far every surface reaches**, so no statement about what *rests* on it
may cut the picture it is found in. The first build clipped the board pass by a stated region,
which this roadmap recorded as deliberate; with a region as small as one around a hole it stops
being deliberate and starts being a statement about a piece deciding how much of the board is seen,
and with it how far its lid is taken to reach. One of the three rectifications a frame costs is now
never narrowed. That is the invariant costing something, which is what an invariant is for.

#### The demonstration, and the direction it states

`watch_narrowing` now states support, then a direction from one of the board's own holes, then the
cube's own colour, and reports what each step leaves *and what a look answering it finds*:

| statement | left to read | reported |
| --- | --- | --- |
| bare | 0.635 m2 | rectangular prism, triangular prism, cube, cylinder |
| supported by the lid | 0.061 m2 | cube, cylinder |
| and in front of the square hole | 0.034 m2 | cube |
| and coloured like the cube | 0.034 m2 | cube |

**The developer's own example was *right of* the square hole, and measuring says that leaves the
cylinder rather than the cube.** On this capture both lid pieces stand to the same side of that
hole along the robot's left-right axis, while the cube stands 25 mm in front of it and the cylinder
40 mm behind, so *in front of* is the direction that tells them apart and it is what the
demonstration states. Both answers are pinned by a test, so the measurement is executable rather
than recorded in prose. *Between the square and the triangle holes* also leaves the cube; *near the
square hole* leaves the cube at 50 mm and both at 100 mm.

**Which hole is where is knowledge and observation together**, and it has to be: this branch's hole
*detector* finds no square hole at all -- the fault `holes-fitted-like-pieces` (#236, on the other
stack) owns. So the board mesh says the layout, the look says where the board stands, and
`recorded_setup.board_holes_in` puts the two together. The naming those holes carry
(`square_hole`, `triangle_hole`, `circular_hole_1`) moved out of `world.py` into `hole_geometry.py`
so the simulated board and a statement about a recording call them the same thing. Worth knowing
for whoever merges #236: it would let the hole be named from the detection instead, and the mesh is
about 15% larger than the board these recordings hold, so a hole placed from it is a hole placed
approximately.

**A colour narrows what is fitted rather than where to look**, so the colour step leaves the same
region and a different picture: the rectified plane with everything but that colour blacked out.
Cube and cylinder are both cyan in this set, so colour alone never separates those two -- what it
narrows is two hues to one and six candidate pieces to two.

#### What it costs

Every row is the same statement answered through the backend, timed against the unnarrowed look in
the same run:

| what the statement says | cost | pieces reported |
| --- | --- | --- |
| nothing | 0.174 s/frame | 20 |
| supported by the lid | 0.28x | 6 |
| in front of the square hole | 0.43x | 6 |
| near the square hole (50 mm) | 0.30x | 5 |
| all three, and coloured like the cube | 0.26x | 5 |

A placement stated on its own is worth about as much as naming a surface, and the two compose. The
floor is the board pass, which is never narrowed.

#### Verification

450 passed, 1 skipped, 11 xfailed across `test/experiments_test/` against 437 on this branch's
previous tip. `test/krrood_test/test_eql/` and `test/semantic_digital_twin_test/test_worlds/test_predicates.py`
come back with a failing-and-erroring set byte-identical to that tip's, 191 lines, diffed by name in
a worktree with its own `*/src` on `PYTHONPATH`. The sdt ORM interface regenerates with
`BetweenDAO`, `NearDAO`, `ColoredDAO` and `PlacementRelationDAO` mapped and imports;
`regenerate_all_orm.py` still stops on `giskardpy`, which needs `rclpy` and reproduces on `main`.

Two API changes updated their own tests rather than being worked around: `StatedRelation` no longer
takes `related_thing` as a constructor argument (the two tests that built one now assert the
relation type and the related thing directly, which is the stronger form), and a look narrowed to a
stretch now reads an overhang past it, which is what its test asserts.


### `search-clipped-to-a-predicates-region`: one statement, read from where the camera stands

Third round, 2026-09-01, at the developer's ask, and it moved three things: which way *right*
is, how the demonstration says what it wants, and what its pictures show.

#### A direction means what it means on screen

The second round read every direction from the world's own frame, so *right of* meant the
robot's right and a person watching the windows had to translate. `RgbdFrame.point_of_view`
turns the camera's optical frame -- x across the picture, y down it, z along the axis it
looks down -- into the convention a pose is stated in, which is what a relation reads its
axes from: x the way the looker faces, y to its left, z up. A direction stated from there
means what the picture shows.

**That alone would have narrowed nothing**, and the reason is worth keeping: a direction read
from where a camera stands runs across the world's own axes, and **no axis-aligned box holds
a half space**. `allowed_space` is right to answer everything there, and useless as a clip.
So `PlacementRelation.allowed_part_of(space)` answers the part of a stretch *already bounded*
that the relation allows -- for a direction, the corners of that stretch on this side of the
dividing plane together with wherever that plane crosses its edges -- and each surface's
search is narrowed against the stretch it was about to read (its own reach, and how high
above it a thing standing on it is reported) rather than against the world. With it, a camera
-relative direction narrows exactly as well as a world-axis one did: 0.036 m² of lid left
against 0.061 unnarrowed, and 0.40x the cost of an unnarrowed look.

The `detect` early exit that refused a look narrowed off the table went with the change. It
contradicted the same method's own rule that the board is found wherever the pipeline looks
at all, and per-surface narrowing does its work: a surface the statement leaves nothing of is
simply not searched.

#### The demonstration is one query, interpreted

`watch_narrowing` assembled its statement from a list of separate conditions and fetched the
lid and the hole out of the world by hand. Both are gone. The statement is written once and
whole, and the things it is about are **described in it** -- the body the world calls the
lid, the body it calls the square hole -- so nothing is fetched before it.

`PerceptionBackend` answers those descriptions out of the domain the statement gave them,
before any look is taken, which is what lets a relation stating one narrow the search exactly
as a relation to a body handed over does. A description no single thing answers is left
unanswered, so the condition stating it stays one the backend refuses rather than one of the
candidates being picked silently. `Match.one_condition_at_a_time()` then reads such a
statement as it grows, carrying whatever it says about anything else through every step,
since a description is what gives a condition its meaning rather than a step of its own.

**One existing krrood test changed with it**, deliberately: a condition about another
variable is refused only when nothing in that variable's own domain answers it. A dangling
description that *is* answerable is now answered rather than refused, which is what native
evaluation would have done with it anyway.

#### Right of the square hole leaves the cylinder, and the pictures now say so

The developer expected *right of the square hole* to leave the cube alone. Measured on
`tracy_pickup_demo`, from the camera's own point of view, it does not: the cylinder stands
34 mm to the right of that hole in the picture and 36 mm below it, while the cube stands
28 mm **above** it and 6 mm to its left. So the demonstration states *above* -- one word --
and a test pins both answers. Neither piece is above the other in the *world*; they rest on
one lid, which is exactly what a direction read from where the camera stands is for.

Two things made the earlier run look as though the narrowing had not worked, and both are
fixed. The rectified window was drawn the way a rectified patch is *indexed*, a quarter turn
from the camera's own view of the table, so a stated direction did not read on screen the way
it was said; it is now drawn through the `ViewFromAbove` the overlay already had. And the
picture reaches an overhang past a stated stretch, so both cyan pieces stayed visible after a
step that reported only one -- the pictures now carry the pieces a look answering that step
found, so what is on screen is the answer as well as the search.

#### Numbers

Over all six captures in one run, against an unnarrowed look at 0.333 s/frame reporting 20
pieces: 0.25x for the surface (6), 0.40x for the direction alone (6), 0.30x for a 50 mm
radius (5), 0.25x for all of them with the colour (5). 460 passed, 1 skipped, 11 xfailed
across `test/experiments_test/` against 450 on the round before; krrood's and sdt's
failing-and-erroring sets byte-identical to it.

## `episode-replayed-into-the-world`: one more player, and the bag it can be measured on

Kicked off 2026-09-01 in `auto` mode, as a draft pull request off
`sdt_segmind_krrood_from_fast_monitor` (#244). The item depends on nothing in this plan and
its note says it can start off `main`; it is based on #244 instead at the developer's
instruction given with the kickoff, so that the segmind detector changes #169 carries - poses
read numerically, regions tracked beside bodies, hole contact events - sit under it rather
than colliding with it later. #244 is the library half of #169 (`semantic_digital_twin`,
`segmind`, `krrood`, and the one `physics_simulators` change the Mujoco adapter needs), split
out in the same session. Re-basing #169 onto it took the native-stack procedure
`stacked-pr-maintenance` records (GitHub refuses a base change on a stack member with a 422):
stack #173 was recorded, dissolved, #169 retargeted, and the stack re-created with #244 at its
foot; the record is on `montessori-eql-stack`, not here. #244 is a draft,
which `check_dependency_readiness.py` would not count as ready to stack on; the developer's
instruction wins over that reading, and the cost is the ordinary one of a stack: this pull
request shows #244's diff until #244 lands.

The session's branch is `claude/episode-replayed-world-kickoff-6ye5bb`, not the manifest's
`segmind_rosbag_player`; the manifest now records what exists. It arrived cut from
`integration` - the #199 hazard, the eighth time on this plan - and was re-cut onto #244's tip
before the first commit.

`check_scope_overlap.py`'s question is answered without it here: no branch on this plan
touches `segmind/players`, and the only in-flight branches that touch `segmind` at all are
#169's stack, whose changes are to the detectors and their tests and are exactly what #244 now
carries underneath this one. Compared by purpose: `montessori_event_replay` (#165) replays a
*recorded demo* - its own event log and video - around queried events in the cramera viewer;
it does not move a world and reads no bag. Nothing to fold.

### What the item is, in one line

A recording of the robot becomes an episode the world can be moved through, so that Segmind
says what happened in it. `EpisodePlayer -> DataPlayer -> FilePlayer` takes a generator of
frames, and a frame is a set of body poses; a rosbag player is one more `FilePlayer` and
`EpisodeSegmenterExecutor` is not changed.

### What a frame is, and where a pose comes from

A bag is a stream of messages on `/tf_static`, `/tf` and `/joint_states`, not frames. The
player samples it: at a fixed period along the recording's own clock it takes a snapshot of
the latest transform of every frame and the latest position of every joint (sample-and-hold),
and that snapshot is one `FrameData`. Its `time` is the bag's time in seconds, so
`DataPlayer`'s real-time pacing works unchanged.

Which transforms become body poses is decided by the world, not the bag. A transform names a
frame; the frame names a body of the world (by the same name, or through an explicit mapping
for a recording whose frame names differ from the world's); and only a body whose parent
connection is a `Connection6DoF` can be posed at all - a robot link's frame, published by the
robot state publisher from the very joint states the bag also carries, is a fixed or revolute
connection in the world and is ignored as a pose. The pose is expressed in the world's root by
composing the transform chain up to the recording's reference frame (`map`), the same walk
`experiments`' `RecordedTransformTree.pose_of` does for the camera; that class lives on #202's
side and reads `rosbag2_py`, so the walk is written once more here, in segmind, and the
duplication is recorded rather than hidden. A body whose chain does not reach the reference
frame in a given snapshot is simply not posed in that snapshot.

Joint states are the second half of a frame. `FrameData` gains `joint_positions`, `DataPlayer`
gains a `get_joint_positions` hook beside `get_objects_poses` (empty by default, which is what
the CSV and JSON players mean), and one frame's poses and joint positions are applied under a
single `World.batch_state_changes()` so the world notifies once per frame rather than once per
degree of freedom. `JSONPlayer`'s dead `get_joint_states` stub goes.

`DataPlayer.process_objects_data` keeps posing only `bodies_with_collision`; the rosbag player
hands it only bodies it can pose, and the filter's reason (a frame-only body has nothing for a
detector to see) holds here too.

### Which library reads the bag

`rosbags`, the pure-Python reader, rather than `rosbag2_py`. Three reasons, in order:
segmind's tests run in CI and in a container with no ROS 2 and must stay able to; the test for
this player has to *write* a bag, since the recordings are 4.7 GB, gitignored and absent from
every container, and `rosbags` writes the same `mcap` files it reads; and segmind is a library
that should not acquire a ROS dependency for a file format. `experiments`' camera reader keeps
`rosbag2_py` because it deserializes camera messages a ROS installation is there for anyway;
two readers over one format is a duplication worth folding later, in that direction.

### What is being built

- `segmind/players/rosbag_player.py`: `RosbagPlayer(FilePlayer)`, a `RosbagTopic` enum for
  the three topics, a transform tree that holds the latest edge per child frame and composes a
  chain, and the sampling generator.
- `FrameData.joint_positions`, `DataPlayer.get_joint_positions`, one batched application per
  frame; the JSON stub removed.
- `rosbags` declared in `segmind/pyproject.toml`.
- Exceptions of their own for a recording that carries none of the three topics, and for a
  reference frame the recording never publishes.

### Deliberately not done here

- **No world is built from the bag.** The player poses bodies of a world it is given, like its
  two siblings; what the world contains is the caller's.
- **The camera topics are not read.** That is `experiments`' recordings module, and a capture is
  the right unit for perception; this item is about motion.
- **No expectation is armed.** What the events mean for where a thing should be is
  `expectations-from-events`.
- **The real bag is not replayed.** Only `tracy_pickup_demo` carries the robot at all (the
  2026-08-31 measurement on this plan), it is not in any container, and the world it needs is
  the Tracy world with the board. That run is the demo's, on the machine that holds the bag; this
  branch makes it a one-line call and records the constraint on the item, as the plan asked.

### The checkable outcome

A bag written by the test with a static edge, a moving free body under it, and a moving joint
replays into a world built for it: the free body's global pose is the composed chain at the
last sample, the joint reads the last position, and the robot link frame changed nothing. Over
the apartment world the detector tests already use, a bag that lifts the milk off its box and
sets it back down yields `LossOfSupportEvent` and `SupportEvent` from an unchanged
`EpisodeSegmenterExecutor`, which is the claim of the item.

### Verification

Tests first, at three levels, so each failure names its own cause: the sampler over a bag
written into `tmp_path` (frame count, times, the latest-wins rule); the mapping from a frame
to bodies and joints of a small hand-built world (the chain, the ignored link, the unknown
frame); the replay end to end (world moved; events logged over the apartment world). Run in
the `uv sync --extra dev --python 3.12` environment, with `--orm-build never` since the
giskardpy generator still stops on `DebugExpressionPublisher` here as on unmodified `main`.
`scripts/format_docstrings.py` over every touched file. The environment this time: the `uv`
on `PATH` is 0.8.17 and fails on the repository's `pyproject.toml`; `pip install -U uv` puts
0.12.8 at `/usr/local/bin/uv`, which builds the workspace; `rosbags`, `black` and
`docformatter` are installed into the venv by hand.

### Landing hazards

None on this plan: no other item touches `segmind/players` or `data_player.py`. On
`montessori-eql-stack`, `montessori_event_replay` edits `test_segmind_detectors.py` heavily and
`segmind/detectors`; this branch edits neither.

### `episode-replayed-into-the-world`: what it took, and what the recording turned out to be

Built as one commit on #246 off #244's tip. Nine new tests in
`test/segmind_test/test_episode_replay/test_rosbag_player.py`; `test/segmind_test` reports
`48 passed, 1 skipped` against `39 passed, 1 skipped` before, which is the nine added here and
nothing else moved. `scripts/format_docstrings.py` ran over every touched file, and black
re-wrapped `json_player.py` on the way, which is the only reason that file's diff is larger
than the four-line stub it removes.

**The plan held.** `RosbagPlayer(FilePlayer)` in `segmind/players/rosbag_player.py` with
`RosbagTopic` and `RosbagMessageType` enums, a `TransformTree` holding the latest edge per
child frame and composing a chain, and a sampling generator; `FrameData.joint_positions`,
`DataPlayer.get_joint_positions` (empty by default) and `apply_frame`, which applies one
frame's poses and joint positions under one `World.batch_state_changes()`; `JSONPlayer`'s
`get_joint_states` stub removed; `rosbags` declared in `segmind/pyproject.toml`; two
exceptions in a new `segmind/exceptions.py`, `RecordingHoldsNothingToReplay` (raised at
construction, from the recording's topic list) and `ReferenceFrameNotRecorded` (raised on the
first frame, once the transform tree has been read up to it). The test dataset gained
`test/segmind_test/dataset/recorded_episode.py`, which writes an episode of static transforms,
timed transforms and timed joint positions into an `mcap` bag through `rosbags`' writer, using
the player's own topic and message-type enums so the test and the code agree by definition.

**Sampling is decided per message, not per frame.** The generator holds the transform tree
and the joint positions as the latest values seen, and before applying a message at time *t*
it emits a frame for every sample time strictly before *t*; after the last message it emits
the samples up to and including the last message time. So a period equal to the message
spacing yields one frame per message and a shorter period repeats the held state between
them, which one test pins. The first sample is taken at the first dynamic message
(`/tf` or `/joint_states`); `/tf_static` is applied whenever it arrives and starts nothing.

**The reference frame is checked on the first frame, not at construction.** Checking it at
construction would mean reading the whole recording twice; a frame that cannot be expressed
in the reference frame is the first thing the replay does, so the error arrives before
anything has moved.

**One thing the plan had not looked at, worth knowing for the demo.** On `main`,
`segmind/datastructures/events.py` imports `geometry_msgs.msg.PoseStamped`, so no segmind test
can be collected without ROS 2 -- the baseline run over the `main` worktree here failed at
collection for all five segmind modules. #244 removes that import (its numeric-pose change
replaced it), which is why this item's tests run in this container at all and a second reason,
after the detector changes, that basing on #244 was the right call.

**`DataPlayer.process_objects_data` keeps posing only `bodies_with_collision`.** The rosbag
player hands it only bodies whose parent connection is a `Connection6DoF`, and the collision
filter holds for the same reason as before: a frame-only body has nothing for a detector to
see. Recorded here because a robot root placed in `map` by `/tf` without a collision shape
would not be moved by a replay; on the demo world the robot stands where the URDF puts it.

**Deliberately left standing.** `experiments`' `RecordedTransformTree` and this
`TransformTree` walk the same chain over two readers (`rosbag2_py` there, `rosbags` here).
Folding is in the direction of `rosbags`, and belongs to whoever next touches the camera
reader.

**The environment.** `/usr/local/bin/uv` did not exist; `pip install -U uv` put 0.12.8 there,
`uv sync --extra dev --python 3.12` built the workspace, and `rosbags`, `black` and
`docformatter` were installed into `.venv` by hand. Tests run with `--orm-build never`, since
the giskardpy ORM generator still stops on `DebugExpressionPublisher` here as on unmodified
`main`; `test_robots/test_pose_facing.py` fails to collect here (a robot type resolves to
`NotSet`), also independent of the branch, and is ignored. `.claude/hooks/plan_item_bootstrap.py
open` failed at `save-plan.sh` exactly as #231, #236, #238 and #239 recorded; worked around by
editing `plan.yaml` directly.

### `search-clipped-to-a-predicates-region`: the review round of 2026-09-02

Resolved 2026-09-02 in `auto` mode. **Nothing was wrong with the branch, and nothing was
running to say so either.** #238 has no CI at all -- a fork pull request based on another
fork branch runs no workflow, so `get_check_runs` and `get_status` both come back empty --
its two dependencies #227 and #232 are open and out of draft, and unlike #222's round there
was no pending review blocking replies. What kept it open was six review threads opened
that afternoon, of which the item's own `blockers` recorded none. That is the fourth time on
this plan that the cause of a stall was a review comment nobody had turned into state, and
writing them down was again the first thing the resolve did, before any code.

Worth adding to what the earlier rounds recorded about that pattern: **an item stacked deep
enough has no CI to be red, so a green pull request says even less here than it did on
#222.** The only signals #238 carries are its review threads and its own local runs.

#### Three answered exactly as asked, and resolved

- `narrowing_relations` explained the economy each of its three relations buys. It now says
  what they are for: *"which surface to search, which part of it to read, and which colour
  to look for."*
- `_is_this_surfaces` is `_is_on_this_surface`. The developer's own reading of it --
  *"this checks if the piece is on the surface right?"* -- is right, and is what the first
  docstring line now says.
- `_POSE_NOUN` and `_frame_noun` moved off `spatial_types.py`'s module level and into
  `_verbalization_noun_phrase_`, where the frame's noun phrase is a value built once rather
  than a function called twice. Nothing else read either of them.

#### The demonstration is one call, and the argument is not quite a query

*"I would like this to just be `show_step_by_step(query)` and all needed things should be in
the source files."* Done as far as it goes: `watch_narrowing.py` is the statement the
demonstration states plus

```python
show_step_by_step(look_for_the_cube_on_the_lid, WatchedCapture.from_command_line())
```

and everything the file used to do itself -- building the world and the pipeline, loading
the capture, finding the board, placing the camera, making the backend, verbalizing, opening
and closing the display -- is `step_by_step.py`'s.

**Where it is answered differently, and why.** The first argument is a function of a look
rather than a `Match` already stated. A statement about this scene is written over things a
world holds (`variable(Body, world.bodies)`, the two hole sub-queries) and over the spot the
look was taken from (`look.seen_from`), and none of those exist until the look has been
taken -- which is precisely what this function is for. A query built beforehand would put
the world, the capture and the board back in the caller's hands, which is the setup the
thread asks to remove. Left open for the developer, per the standing convention.

Two values carry what was setup. `WatchedCapture` is which shipped capture is watched, where
the captures lie and whether anything is drawn, and reads all three off the command line;
`RecordedLook` is the world, the pipeline, the pictures, the board they show and the spot
they were taken from. And **finding the board moved onto the pipeline**: `board_in` belongs
to whatever rectifies the plane the board stands in, and `detect` now reads it there rather
than spelling the same two lines a second time.

#### Two design asks that reach past this item, both put back to the developer

**"Why does evaluating a query need a pipeline?"** The honest answer is that
`MontessoriPerceptionPipeline` is the residue of everything not yet knowledge-directed. Of
its six fields, `table`/`lid` and `world`/`reference_frame` are knowledge that `of_world`
already reads from the world -- a recording simply has no world, which is why
`recorded_setup` writes them down -- `headroom` is #239's to conclude, and only the two
detectors are genuinely hand-wired. A backend taking the request, the camera and the frames
alone needs three things that are already items: `surfaces-found-by-looking` for surfaces
read from the picture rather than from a model, #231 for which detector answers, #239 for
the numbers it answers with.

On the EQL-RDR half, checked live rather than repeated: **#159 is open, out of draft and
carries no blocking label; #77 is open, out of draft and `mergeable_state: clean` but
carries `integration-conflict`.** So the engine is available to stack on, and what it would
buy here is not the detector choice (#231 has that with EQL-native rule trees) but a rule
tree concluding *how to answer a look*, grown by an expert when a new kind of request turns
up. What it costs on this branch is what #231 already refused: 9,236 lines over 50 files
merged into a pull request whose own change is a few hundred. Proposed as an item of its own
-- *"a look is planned from the request, not configured"* -- and not added, since adding one
is structural and the developer's.

**"Rename to `DetectedMontessoriShape` and make it a `Role` for `MontessoriShape`."** The
rename is 51 references across 10 files and mechanical; the role is not. `Role[T]` is pure
composition and takes its role taker explicitly, so every detection would need a
`MontessoriShape` -- a `HasRootBody` annotation over a body in a world -- and a look reports
what it saw before anything of the sort is in the world. **Spawning what was found into a
copy of the world is `imagination-world-rejects-what-a-predicate-refuses`**, the sibling
item from the developer's own r3893499716, so the ask is right and the mechanism it needs
belongs there rather than here. It would also close the gap #227 left open: a detection that
*is* a role of a world entity gives every predicate a real subject, so nothing has to be
refused for want of one. Three ways to take it were put to the developer -- rename here and
role there, both there, or both here -- with both-there recommended and none taken.

#### Verification

**467 passed, 1 skipped, 11 xfailed** across `test/experiments_test/` against **464 passed,
1 skipped, 11 xfailed** on this branch's previous tip in the same container, which is the
three tests this round adds and nothing else moved. `semantic_digital_twin`'s
failing-and-erroring set over `test_spatial_types.py`, `test_predicates.py`,
`test_color.py` and `test_prefixed_name.py` is byte-identical to that tip's, 14 lines,
diffed by name.

Six of the experiments modules do not collect at all under `--noconftest` --
`test_control_loop_benchmark`, `test_control_loop_runtime`, `test_montessori_bag_replay`,
`test_real_stretch_demo_process_boundary`, `test_sage10k` and `test_scalability`, each
needing ROS or `rosbag2_py` -- and were excluded from both sides of the comparison. That is
this container rather than the branch: `test/experiments_test/conftest.py` imports `rclpy`,
so a run of that directory with the conftest cannot start here at all.

#### The environment, which is different again for the fifth time

`/usr/local/bin/uv` does not exist in this container either and the `uv` on `PATH` is 0.8.17,
which cannot parse this repository's `pyproject.toml`; `pip install -U uv` puts 0.12.9 there
and `uv sync --extra dev --python 3.12` builds the whole workspace. `black` and
`docformatter` are not in the dependency set and go in by hand, with the virtual
environment's `bin` on `PATH`, before `scripts/format_docstrings.py` will run.

## Two structural changes out of #238's round (2026-09-02)

Both are the developer's decisions, taken the same day the round was resolved, on the two threads
that reach past `search-clipped-to-a-predicates-region`.

### A new item: how a look is answered is concluded, not configured

r3915356623 — *"why does evaluating a query needs a pipeline? why do we need anything specified
other than the request and the camera and the feed (images input)?"* — becomes
**`how-to-look-concluded-from-the-request`**, in the `request-language` track, depending on
`choose-detection-method` and `detector-parameters-from-knowledge`.

What settled it is what the pipeline turns out to be. `MontessoriPerceptionPipeline` has six
fields and they are not one kind of thing: `table`/`lid` and `world`/`reference_frame` are
knowledge `of_world` already reads from the world, `headroom` is #239's to conclude, and only the
two detectors are genuinely hand-wired. **The pipeline is the residue of everything not yet
knowledge-directed**, rather than a second configuration surface beside the world — so the ask is
not a redesign of the backend but the last step of the three items that between them empty it.

The item's own work is the piece none of those three covers: a rule tree concluding *how to answer
a look* from the request — which detectors run over which surfaces — grown by an expert when a new
kind of request turns up. That is the half of #231's *"extensibility with new situations through
interaction with an expert"* that #231 answered only for the choice of detector.

It stacks on **#159** and reaches it through #239, which already merges #159 in. Doing it on #238
was refused for the reason #231 refused it: merging #159 there adds 9,236 lines over 50 files to a
pull request whose own change is a few hundred. Live state that day, checked rather than repeated
from the 2026-08-31 correction: **#159 open, out of draft, no blocking label; #77 open, out of
draft, `mergeable_state: clean`, carrying `integration-conflict`.**

`surfaces-found-by-looking` is deliberately *not* a dependency. Surfaces are already read from the
world, so a live look needs nothing from it; what that item removes is the last model-read surface
for a *recording*, and this item can be demonstrated without it.

### The detection becomes a role, in the item that can give it a role taker

r3915631447 — rename `MontessoriShapeDetection` to `DetectedMontessoriShape` and make it a `Role`
for `MontessoriShape` — is folded into
**`imagination-world-rejects-what-a-predicate-refuses`**, both halves, rather than split across
that item and #238.

`Role[T]` is pure composition and takes its role taker explicitly, so every detection would need a
`MontessoriShape` — a `HasRootBody` annotation over a body in a world — and a look reports what it
saw before anything of the sort is in the world. Spawning what was found into a copy of the world
is precisely what that item builds, so it is where a role taker first exists.

Doing the rename alone on #238 was the cheaper-looking option and was refused on two counts: it is
51 references across 10 files that #232, #236 and #239 would each inherit as a conflict, and the
type would be named twice — once now and once when it becomes what it will finally be.

**It also closes the gap #227 left open, by construction.** A look reports sightings rather than
the things a relation is written over, which is why `relations_hold` re-checks only the relations
the backend narrowed by and refuses any other. A detection that *is* a role of a world entity
gives every predicate a real subject, so nothing has to be refused for want of one — which is the
same thing that item's rejection sampler needed, arriving as a type rather than as a mechanism.

### `perception-backend`: the restack of 2026-09-02, and a conflict that was not its parent's

Resolved 2026-09-02 in `auto` mode. **This is the first stall on this plan that was not a
review comment.** The four before it — `surfaces-from-world`, #222's own round,
`choose-detection-method`, `search-clipped-to-a-predicates-region` — were each a comment
nobody had turned into state. This one was the opposite: every one of #222's nine review
threads is now resolved, including r3893312001 and its two follow-ups that the item recorded
as deliberately open, so its own `blockers` had gone stale in the other direction, describing
an obstacle that had since been cleared. CI was green on all 23 checks and the pull request
was out of draft.

What actually withheld it was `mergeable_state: dirty` and the `needs-resolution` label the
maintenance routine set at 00:45 that morning, reporting that
`perception_per_supporting_surface` would not merge in. **Worth recording as a signal in its
own right:** that label is machine-set state that says exactly what is wrong, and unlike a
review thread it also removes the branch from every later promotion pass, so a branch carrying
it is stalled silently rather than noisily.

#### The conflict was with `main`, not with #221

The parent's tip had moved only by taking `main` in — `5d3615b1` merging `6a2f1199`, the
`eql-probabilistic-qa` work — so none of the three conflicted files were touched by
`detect-per-supporting-surface` at all. Every conflict was `main`'s probabilistic-query work
meeting this branch's own additions to `backends.py`, `exceptions.py` and
`vocabulary/english.py`: two sides adding beside each other, neither changing what the other
wrote. All three were resolved by keeping both, and the merged result needed no new code.

The one place the two sides genuinely met is `Directive`. `main` had rewritten its docstring
for `DISTRIBUTION_OVER`, whose point is that it is *not* an imperative — *"the two imperatives
ask for rows, the third asks for a description of the query"* — while this branch had added a
third imperative, `LOOK_FOR`. Keeping `main`'s framing and correcting the count is what makes
the enum readable with all four members in it; keeping this branch's "the imperative verb that
opens a request" would have been wrong about `DISTRIBUTION_OVER`.

#### What this says about the stack

`main`'s entity query language moves under every branch in the `request-language` track, and
this is the first time it has landed on one. #227, #238 and everything stacked past them will
meet the same three files when the merge reaches them, and the resolution is recorded here so
it is not re-derived four times.

#### Verification

`test/krrood_test/test_eql/`: **1110 passed** against **1087** on this branch's pre-merge tip
`9eb4d747` — the 23 probabilistic-query tests the merge brings in — with a failing-and-erroring
set identical to that tip's, **178 lines on both**, diffed by name rather than compared by
count. The baseline was taken in a worktree with its own `*/src` on `PYTHONPATH`, the precaution
this branch's previous round recorded after nearly measuring itself against itself.
`test/experiments_test/`: **362 passed**, 1 skipped, 16 xfailed, unchanged by the merge.

`--continue-on-collection-errors` was needed on both sides: `test_backends.py` imports the
generated ORM interface, which is absent here, and it is one of the 178.

#### The environment, for the sixth time

`/usr/local/bin/uv` does not exist in this container until `pip install -U uv` puts 0.12.9
there, and the `uv` first on `PATH` is 0.8.17, which cannot parse this repository's
`pyproject.toml` — so the working `uv` has to be called by its full path rather than found.
`black` and `docformatter` are again not in the dependency set and go in by hand.

### `episode-replayed-into-the-world`: the review round of 2026-09-03

Resolved 2026-09-03 in `auto` mode. **Nothing was wrong with the branch.** #246 was green on
all 23 checks, `mergeable_state: clean`, out of draft nowhere — it is a draft as this
plan's convention asks — and its base #244 open, out of draft and clean. What kept it open
was four review threads opened that afternoon, of which the item's own `blockers` recorded
none. That is the **fifth** time on this plan that the cause of a stall was a review comment
nobody had turned into state, after `surfaces-from-world`, #222's own round,
`choose-detection-method` and #238; the only stall that was not one is #222's restack.
Writing them down was again the first thing this resolve did, before any code.

Unlike #238, this branch does have CI — it is one deep off #244 rather than deep in a fork
stack — so the green run is worth something here. It still said nothing about why the item
was open.

#### The generator was one method holding four pieces of state

The ask, in the developer's words: *"this method is so complicated and big, I do not like
nested methods. Modularize, simplify and clean this, do very small modular methods, use OOP
and abide to SOLID."* `RosbagPlayer._sample` was fifty lines with two nested functions
(`next_sample_time`, `frame_at`) closing over `tree`, `joint_positions`, `first_sample_time`
and `sample_count`, and a three-way branch on the topic inside the message loop.

The nesting was the symptom rather than the fault: **a closure is what you write when the
state has no object to belong to**. Three now:

- `RecordedMessage` — a message with the topic it arrived on and the instant of the
  recording's clock it was published at. `RecordedMessage.of` is the one place that knows
  how the reader hands a message over, and it replaces the `(connection, timestamp, raw)`
  tuple whose positions carried the meaning.
- `RecordedState` — the transform tree and the latest joint positions together, which is
  what the two closures both reached for. `record(message)` keeps a message as the latest
  word and `frame_at` takes a frame of the state as it stands.
- `RecordingSampler` — the sampling itself, with the counters as fields. `frames`,
  `_messages`, `_replayed_connections_of`, `_frames_due_before`, `_frames_due_through`,
  `_next_sample_time`, `_take_sample` and `_require_a_recorded_reference_frame`; the longest
  is seven lines.

**The branch in the loop moved onto the type that owns it.** `RosbagTopic.advances_the_clock`
says whether a message on a topic states a time to sample along, so `/tf_static` needs no
`continue` and `frames()` reads as the rule rather than as the special case.
`RosbagTopic.message_type` is the same move for the pairing the writer used to restate beside
every `add_connection`. Worth generalizing: **the branches worth moving onto an enum are the
ones that ask what a member *is*, not the ones that ask what to *do* about it** — both of
these answer a property of the topic, and both had been written out at every use site.

Behaviour is unchanged, and the split of eager and lazy that the item's own section records
is preserved deliberately: the topic check still happens when the player is built (the
sampler's `replayed_topics` opens the reader eagerly) and the reference frame still on the
first frame. Both have the tests they already had.

#### The strings were a type, and the type needed a test rather than a promise

*"make these string keys StrEnum members instead, and all similar ones. and import them and
reuse them everywhere they are needed."* The six ROS message type names
`recorded_episode.py` spelled as dictionary keys are `RosbagMessageType` members beside the
two already there, so the enum is now every message type a recording carries rather than
only the two published on a topic, and the reader and the writer name them from one place.

**A name in an enum is not automatically a name that resolves**, which is the fault an enum
of foreign identifiers can still have: a typo surfaces as a `KeyError` at the one call site
that uses that member, whenever that site next runs.
`test_every_message_type_named_is_one_the_recordings_definitions_hold` asserts every member
against the type store the recording is read and written through, so all eight are checked
by one test rather than incidentally by whichever call site happens to be exercised.

The sweep for "all similar ones" turned up two more bare strings naming a fixed thing — the
empty `frame_id` a joint state message carries (`UNSTAMPED_FRAME`) and the frame the refusal
test roots its tree in (`UNROOTED_FRAME`) — and one convention being trusted rather than
declared: `_write` depends on both published kinds having a `time` and a `to_message()`, so
they share a `PublishedMessage` base that says so.

#### Docstrings, and the two places left bare on purpose

Two threads asked for the missing docstrings and type hints, one on the player and one on the
whole pull request. Swept with an AST walk over every file the pull request touches rather
than by eye, which is what found the remaining two: the JSON player's `_pause` and `_resume`
stubs, and — in the tests — every test function and helper.

`TransformTree.record` had no hint at all. It takes a message of a type `rosbags` generates at
import time, so there is no class to name: it is `Any`, with the docstring naming
`RosbagMessageType.STAMPED_TRANSFORM` for what it actually is. **Worth knowing for anything
else reading a bag in this workspace:** the deserialized message types are not importable, so
`Any` plus a docstring is the honest hint, and `rosbags.interfaces.Connection` — which *is*
importable — goes under `TYPE_CHECKING`.

**Two places are left undocumented deliberately and the thread is left open for the
developer**, per the standing convention about answering differently: the two new exceptions'
`error_message` / `suggest_correction` overrides, whose contracts `DataclassException` states
on its abstract methods and which no `DataclassException` subclass anywhere in this workspace
documents; and `DataPlayer.__post_init__` / `FilePlayer.__post_init__`, which this branch
neither adds nor changes and which show in the diff only because black re-wrapped lines
around them.

#### Verification

`test/segmind_test`: **53 passed, 1 skipped** against **48 passed, 1 skipped** on this
branch's previous tip, which is the five added here and nothing else moved.

**The five are mutation-checked rather than merely green**, since a refactor's own tests are
worth what they would catch: sharing the joint positions instead of copying them, making
every topic advance the clock, and making every topic claim the transform message type each
fail their own test and nothing unrelated. The middle one is the one worth recording — the
sampling tests all still pass under it, because this recording's static transform happens to
be stamped at the first dynamic message time, so `advances_the_clock` is a rule that only its
own test observes on this data.

#### The environment, which is the easiest this plan has recorded

The `uv` on `PATH` is 0.8.17 and cannot parse this repository's `pyproject.toml`, as five
consecutive items have recorded; `pip install -U uv` puts 0.12.9 at `/usr/local/bin/uv` and
`uv sync --extra dev --python 3.12` builds the whole workspace, **including `rosbags`** — the
item's own section had to install it by hand, and it now comes with the sync since this
branch declares it. `black` and `docformatter` still go in by hand, with `.venv/bin` on
`PATH`.

`.claude/hooks/plan_item_bootstrap.py` was not used at all this round: the version in this
branch's checkout has only `record` and `open`, not the `update` the resolve skill now calls
for, so `plan.yaml` was edited directly and pushed with `save-plan.sh --manifest`. That is
the sixth round on this plan to work around that script, and the second distinct reason —
the indentation fault #231, #236, #238, #239 and this item's own kickoff hit is one; a
checkout older than the skill that calls it is another.

## `imagination-world-rejects-what-a-predicate-refuses`: the plan, and the world a sighting is given a body in

Kicked off 2026-09-03 in `auto` mode, as pull request #255. Dependency
`perception-predicates-guide-the-search` (#227) reports `open_ready`, so it is ready to
stack on.

### It is based on #238, not on #227, and that is what the fold decided

The item's `depends_on` names only #227, but the rename folded here on 2026-09-02 is
counted on **#238's** tree: 53 references across 11 files there against 21 across 5 on
#227, and the item's own note says "51 references across 10 files" -- #238's tree, a day
earlier. Six of those files (`occupancy.py`, `step_by_step.py`, `watch_narrowing.py` and
three test modules) exist on #238 and not on #227. Renaming on #227 would therefore name
the type on half its readers and hand #238 the other half as a conflict, which is the one
outcome the fold was taken to avoid. So `search-clipped-to-a-predicates-region` is a real
dependency of this item and is recorded as one.

### What is actually refused today, measured rather than assumed

`PerceptionBackend._check_what_was_found` refuses a condition in exactly one case: it
constrains a variable besides the thing sought, that variable is not one the statement
described out of the world, and the look does not narrow itself by the relation
(`narrowing_relations`, which for the Montessori backend is `SupportedBy`,
`PlacementRelation` and `Colored`). Everything else it keeps as a residual condition and
re-evaluates natively.

That leaves two distinct faults, and the role fixes both:

- **A relation stated about the thing sought and something the world holds** -- *in
  contact with the board* -- is refused outright, because the look reports a sighting the
  relation has nothing to be written over.
- **A relation stated about the thing sought alone** -- *supporting something* -- is not
  refused at all: it is kept as a residual and evaluated natively, where it reaches for
  `_world` on a dataclass and raises. A refusal that is not even a refusal is the worse
  half of the same fault.

### What is built

1. **`DetectedMontessoriShape`**, a `Role` for `MontessoriShape`, replacing
   `MontessoriShapeDetection`. The role taker is the piece as the world would hold it: a
   `HasRootBody` annotation over a body carrying the known piece's own geometry, standing
   at the pose the look measured.
2. **The imagined world**: one look spawns what it recognised into a copy of the world it
   was taken in, so the original world is untouched and every detection has a subject.
   Where the pipeline has no world, the copy is an empty one -- a sighting still needs a
   body to be a body.
3. **A relation the look could not narrow itself by is checked over what came back**
   instead of refused, which is one change in `krrood`: the things a statement described
   are pinned to the domain that answered them, so a condition relating the thing sought
   to one of them evaluates natively. A condition constraining a variable that is neither
   the thing sought nor described stays refused -- there is still nothing to evaluate it
   against.
4. **What the statement rejects is deleted**, through a `discard` on `PerceptionBackend`
   that does nothing by default and, for the Montessori backend, removes the rejected
   detections' bodies from the imagined world. The world a look leaves behind is then
   exactly the answer.

### Deliberately not built here

- **Answering a description out of the look itself** -- *left of another object that has a
  cyan colour*, where the other object is also only found by looking. It needs the second
  variable to be answered by the same look rather than out of the world, which is a
  mechanism of its own beyond giving a sighting a body, and the budget section directs
  every item to the narrowest form that demonstrates its claim.
- **Re-reading the narrowing relations against the bodies.** `relations_hold` still checks
  a placement as a point and support by the surface's name, which is what the look
  established. Reading them off the spawned bodies instead is a change to what #238 built
  and is left to it.

### Verification

Tests first, at two levels so each failure names its own cause:

- **`krrood`**, through the existing mimic `BackendThatLooksAtTheWorld` and its dataset
  module, per krrood's self-containment rule: a statement stating a relation the look does
  not narrow itself by is answered rather than refused; a sighting the relation rejects is
  neither returned nor left in what the backend holds; a condition over a variable neither
  sought nor described still raises `BackendCannotResolveCondition`.
- **`experiments`**: a detection is a role whose taker stands at the measured pose in the
  imagined world; the world the look was taken in is unchanged by it; and, end to end over
  a capture, a statement stating a relation the backend cannot narrow itself by is answered
  by evaluating it against the spawned bodies.

Run under the environment five previous items recorded: `pip install -U uv` first, since
the `uv` on `PATH` is 0.8.17 and cannot parse this repository's `pyproject.toml`, then
`/usr/local/bin/uv sync --extra dev --python 3.12`.

### Landing hazard

The rename touches `occupancy.py`, `pipeline.py` and `detections.py`, which #232 and #236
also change; they meet it when the merge reaches them. That cost was weighed when the fold
was taken and is why the rename happens once, here, in the name the type will finally
carry.

## `expectations-from-events`: three parents, three stacks, and the rule that carries the weight

Kicked off 2026-09-03 in `auto` mode, as draft pull request #257 off
`claude/plan-item-kickoff-kdp-o4l189` (#232). All three dependencies are open and out
of draft, so `check_dependency_readiness.py` reports `open_ready` for each. The
session's branch arrived cut from `integration` -- the hazard #199 exists to refuse,
and the ninth time on this plan after #223, #225, #227, #232, #236, #238, #239 and
#246 -- and was re-cut onto #232's tip before the first commit.

### It is the one item on the deadline's critical path with no branch, and another plan says so

`icra-experiments` (tracking issue #252) recorded on 2026-09-03 that everything this
plan has built is consumed by its `integrated-simulation-pipeline`, and that
`expectations-from-events` is the one thing it still needs and "the one item of this
plan on the deadline's critical path that has no branch yet". It blocks that plan's
`failure-taxonomy-and-typing` (its expectation-derived failure type) and
`experiment-c-in-simulation` (which without it "reports typed failures but not detected
ones"). Both carry a blocker naming this item.

That plan also records an open question for the developer, repeated here rather than
answered: whether this item is still needed once `snapshot-working-memory` and
`failure-taxonomy-and-typing` exist, or whether the violated-expectation report folds
into the failure typing there. It is not this session's to settle, and the recorded
answer everywhere else is that the item is needed, so it is built.

### Three dependencies on three stacks, and the base that costs least

This is the second item whose dependencies span the plan's two perception stacks, and
the first whose third is on a stack of its own:

```
#202 -> #205 -> #221 -> #222              the backend, and what a look is asked for
                     \-> #225 -> #232     the believed place, and hypotheses
#244 -> #246                              the events, read off a recording
```

The base is **#232**, because the type this item extends is defined there: #232's own
section records the belief sources it built and names "the object's own history" as the
fourth, which is this item. **#222 and #246 are merged in rather than waited on**, this
plan's standing `depends_on` rule and the same move #227 made with #229 and #238 with
#232.

Measured before the branch was opened rather than assumed:

| merge | cost |
| --- | --- |
| #246 into #232 | clean |
| #222 into #232 | `pipeline.py` and `test_montessori_perception.py`, five hunks |
| #246 into #238 | `reasoning/predicates.py` and its test -- #244 against #229 |

The five hunks are the merge #238 already paid and recorded ("both resolve as a
union"), so the resolution is read from there rather than re-derived. The only file
#222 and #246 both touch is `english.py`, which auto-merges.

**Basing on #238 instead was measured and refused.** It already carries #222, #227,
#232 and #229, so it would have cost one merge instead of two -- but it would carry
#227's and #238's 6,853-line diff through this item's review, which is exactly the
trade #231 refused for #159 and #238 refused again. A merge is mechanical and cheap;
another item's diff in this one's review is not.

**#246 is not only the replay.** `segmind/datastructures/events.py` on `main` imports
`geometry_msgs`, so no segmind test collects without ROS 2 -- #246's own round measured
that. #244, which #246 carries, removes that import, so merging #246 is what makes the
event half of this item testable in a container at all. That is a second, sharper
reason for the dependency than the replay, which this item does not run.

### What an expectation is, and what propagates it

The item's widening of 2026-08-31 already settled the type: an expectation is a belief
about where an object is -- a stretch of a named surface, an interval of turns, and the
surface it should rest on -- which is #232's `BelievedPlace` exactly. What this item
adds is the *subject* and the *history*: a `BelievedPlace` about one piece the world
names, and the rules that move it.

Three rules, and they are the item's own notes rather than a design taken here:

- released over a hole, the piece is believed at that hole, turned any way, within the
  spread a release allows;
- still grasped, its pose is the gripper's;
- acted on by nothing, its pose is exactly where it was last seen.

**The third is the one that carries the weight**, and it is why a history makes
tractable what a single frame does not: a belief only decays when something acts on the
object, so an expectation stays good across every frame in which nothing happened.
Segmind's events are what say that something happened -- `SupportEvent`,
`LossOfSupportEvent`, `PickUpEvent`, `PlacingEvent` and `InsertionEvent`, all of which
already exist and are already computed over `is_supported_by`. A gap found in Segmind
is a finding for this item, not an assumption of the plan.

### The violated part is the report, and it is what a recovery acts on

An expectation states three things -- the surface, the position, the turn -- so a look
that contradicts it contradicts one or more of them by name. The insertion promised the
cube would end up *in* the hole; it is found resting *on* the lid, turned thirty degrees
from where it would have had to be. Reporting *which* part failed is what distinguishes
this from an absence, and it is the paper's end-to-end story.

**Recovery is not built**, per the budget section's own narrowing of this item: "report
the violated expectation. Let recovery be the plan re-asking, not a policy of its own."

### How an expectation reaches a look

Through the request. `perception-backend`'s note on #201 states it: "arming an
expectation reaches the pipeline through the request", and the plan's structural change
of 2026-08-31 predicted the shape -- "`SceneRequest` will need to carry a believed place
as well as a type and a surface". So `SceneRequest` gains what is expected, and
`MontessoriPerceptionPipeline.detect` evaluates it beside what `expected_pieces()`
already believes from the world.

This is also what #232's measurement asked for. It built the board's holes as a source
of hypotheses, measured it twice and left it out, recording that "sweeping every hole
for every piece every frame is a second exhaustive pass, not knowledge-directed search;
what makes a seeded fit cheap and precise is a belief that names *which* piece at
*which* place, and the two things that can say that are the world and the object's own
history". This item is that second thing.

### `InsertMontessoriShapeAction` is not edited, and it cannot be

The action exists only on `tracy_icra` -- `git ls-tree` finds it on no branch this item
can base on -- and `ActionDescription` on `main` declares its effect as a
`post_condition` returning a symbolic expression, with no per-action effect this item
could read. So the declared effect is built as a rule this item owns, which whoever
performs the action calls, and the wiring lands on the demo branch. That is the same
split the perception node already has, and `experiments`' own conventions for a module
that cannot be imported in a container.

### The lid marks, and why the captures can be measured at all

#232 left four expected-to-fail marks on `test_every_piece_resting_on_the_lid_is_found`
naming this item, and recorded exactly why they could not come off there: "a capture
carries no world, so nothing on a capture believes anything about the lid yet."

Three of the six captures -- `stuck_cube_in_hole`, `disoriented_cube_on_hole` and
`displaced_cube_from_hole` -- are a cube an insertion put at a named hole, which the
2026-08-31 measurement recorded as needing no replay at all: a hole is a place the board
mesh gives and the board detection locates every frame. So the history for a capture is
stated the way `recorded_setup` already states its surfaces and its camera: *what was
done*, not where the piece is. That distinction is load-bearing and is stated in the
test's own docstring -- stating that an insertion released the cube over a named hole is
a statement about what the recording is, and the look still has to find the piece.

**Whether all four marks come off is a measurement, not a promise**, and is recorded
with whatever it turns out to be, following what #232 and #236 both did with their own.

### Verification

Tests first, at three levels, so each failure names its own cause:

- The expectation and the store on their own: a release over a hole believes the piece
  at that hole turned any way; a pick-up moves the belief onto the gripper; an event
  about another object leaves a belief where it was; a support event confirms and a
  loss-of-support refutes.
- The report on its own: an expectation met; one violated in the surface, one in the
  position, one in the turn; and nothing found at all, which is its own outcome rather
  than a fourth violated part.
- The pipeline over the rendered scene and then the captures, which is the measurement
  that matters.

Cost as a ratio to a same-run baseline, never in seconds, per what #232 recorded about
this container's speed moving between runs by more than the difference being measured.

### Landing hazards

#255 (`imagination-world-rejects-what-a-predicate-refuses`, kicked off the same day on
the #238 stack) renames `MontessoriShapeDetection` to `DetectedMontessoriShape` and
makes it a `Role`, touching `occupancy.py`, `pipeline.py` and `detections.py`. This
branch edits `pipeline.py`, so it inherits that rename the same mechanical way #232 and
#236 do. #223's `Footprint` -> `RectifiedFootprint` rename conflicts with this branch's
`pipeline.py` edits as it does with #205, #221, #225, #232, #236, #238 and #239, and
#231's `LoosePieceDetector` -> `EdgeFitDetector` rename with them.

### The bootstrap script's fault, for the sixth time and in both of its forms

`.claude/hooks/plan_item_bootstrap.py open` failed inside `save-plan.sh` again, with the
error swallowed by `capture_output=True` -- the four-space `ITEM_FIELD_INDENT` against
this plan's two-space item fields, exactly as #231, #236, #238 and #239 recorded, and
this checkout also has only `record` and `open` rather than the `update` the skills now
call for, which is the second distinct reason #246 recorded. Worked around a sixth time
by editing `plan.yaml` directly and pushing with `save-plan.sh --manifest`. It is the
same family as #160 and still wants its own bug-fix pull request.

### The tracking-issue subscription could not be armed

`subscribe_pr_activity` on #201 was refused by this session's permission classifier. The
gathering procedure says not to let that fail the skill, so it is recorded here instead:
this session will not see structural changes to the plan as they arrive, and read the
tracking issue's comments directly before any later round. Reading them at kickoff is
what turned up `icra-experiments`' cross-plan record above, which nothing in this plan's
own roadmap carried.

## `surfaces-found-by-looking`: the surface described, and the model it is measured against

Kicked off 2026-09-03 in `auto` mode, as pull request #259. Both recorded dependencies
report `open_ready`: `perception-backend` (#222) and `surface-finish-annotation` (#216).
The session's branch arrived cut from `integration` rather than from anything this plan is
stacked on -- the hazard #199 exists to refuse, and the ninth time on this plan after
#223, #225, #227, #232, #236, #238, #239 and #246 -- and was re-cut onto #231's tip
before the first commit. Subscribing to the tracking issue was refused by the session's
permission classifier, so this round has no push channel for concurrent structural
changes; the manifest delta is the only one it reads.

### It is based on #231, and that is a third dependency rather than a convenience

The item's `depends_on` names #222 and #216, which between them would base this on
`perception_eql_backend` with #216 merged in. That is wrong twice over, and both reasons
are about work #231 has already done:

- **The properties this item's description of a surface is written over are #231's
  fields.** `WorkspaceSurface.finish` and `WorkspaceSurface.color` -- read off the widest
  horizontal collision shape, which is #216's own recorded design for where a finish is
  read -- exist on #231 and on no earlier branch. #216 puts `SurfaceFinish` on `Shape`;
  it is #231 that carries it as far as the surface perception measures.
- **The mechanism is #231's.** A member of a detector family declaring what it can answer
  as an entity query language condition (`PieceDetector.capability`), and a rule tree
  stated once and grown while in use (`DetectorRules`, `add_rule`,
  `ConclusionSelector.insert_at`), is exactly what this item applies to surfaces. Writing
  a second copy of it on a branch that cannot see the first is the duplication these notes
  record five times over.

#231 carries #216 already -- `80100bd4` is in its history through `e382e581`, though not
through #216's current tip, which has since merged `main` again -- so both recorded
dependencies arrive with it. `depends_on` now names all three, following what
`perception-backend`'s own section did when its dependency on #221 turned out to be
recorded in prose and never in the manifest.

The mechanical scope check reports every path this touches absent from `main` and shared
with #222, #231, #238 and #239, which every round on this plan has already recorded as
expected: every file in this plan is introduced by #202, so path overlap alone would fold
the whole plan into one item. The purpose check is the one that decides it and it comes
back clean: #231 chooses which detector reads a *piece* off a surface the world hands it,
#239 concludes the numbers that detector reads with, #238 clips the picture a stated
relation allows. None of the three measures a surface. What remains once their edits are
removed is a surface found in the image, which no earlier item states in any form.

### What the item is, in one line

`recorded_setup.searched_workspace()` is a rectangle a person dragged sliders to arrive at,
and `WorkspaceSurface.of_body` is the body's own collision shape. Neither is a measurement
of where the table is. This replaces both with a surface described by what the twin states
about it -- a large horizontal plane, mirror-finished, colourless, of about the modelled
size -- and a finder compiled from that description.

### What is built

- **`SurfaceFinder`**, the family, each member declaring the surfaces it can find as an
  entity query language condition over what the world describes, exactly as
  `PieceDetector.capability` declares the looks a detector answers.
- **Two members, which is the demonstration.** Reading the surface off the world's model
  is the base rule and the general answer: it needs nothing of the picture, only that the
  world models the body at all. Measuring the plane in the depth image is the refinement,
  and it holds only for a surface the world describes well enough to recognise one --
  which is what makes the description load-bearing rather than decorative.
- **`SurfaceRules`**, the live tree over that description, stated once and grown through
  `add_rule`, following what #231's review round settled about a tree that is built where
  it is read.
- **The pipeline and the recorded setup ask the rules** for each surface rather than
  reading a tuned rectangle, so the stretch of table searched is measured.

### The evidence this starts from, so the failed half is not re-run

The point-cloud trial of `4b74460f8` measured a RANSAC plane holding 34% of 693k points on
the bare steel and 69% with a mat, table points scattering about 17 mm either side of it,
and **no piece standing out of that cloud at all**. So a plane fit is a candidate for the
surface and is known not to be one for what rests on it; the same trial's clustering must
not be re-run for pieces. Across the six captures everything detected lies within
x 0.57..0.91 and y -0.02..0.37, against a searched region of x 0.35..1.35, y -0.45..0.75 --
the great majority of what is rectified every frame is floor.

### Where the description's own facts come from, and what #239 owns

A rule reading *mirror-finished* needs something to state a finish, and #231 recorded that
**nothing in this workspace states one**. #239 is the sibling off #231 that fixes it, and
it has already landed that half: the lid states hue 19 and `SurfaceFinish.MATTE`, Tracy's
table its own near-colourless grey and `SurfaceFinish.MIRROR`.

That is #239's for the *world*, and it stays there. A recording carries no world, which is
why `recorded_setup` writes down what the recordings were taken over, so this branch states
the recorded table's finish and colour beside the `TABLE_HEIGHT` already there. The two are
complementary rather than duplicates -- the same shape as `BOARD_SCALE_AGAINST_THE_MESH`
sitting in `recorded_setup` on #236 -- and whichever of the two branches meets the other
first keeps #239's statement for the world. Merging #239 in to get it was refused for the
reason #231 refused it: #239 carries #159, which adds 9,236 lines over 50 files to a pull
request whose own change is a few hundred.

### Deliberately not attempted, each recorded rather than dropped

- **Fitting anything but the surface.** The trial above measured that no piece stands out
  of the cloud, so a plane fit is not a piece detector and this branch does not make one.
- **The lid's extent.** #221 took the lid's height from the world and its extent from the
  board detection because the world's board pose has drifted, and #238 recorded the same
  split for a clip. Measuring the lid's own plane here would reintroduce exactly the
  constant that split removed.
- **Removing `tune_workspace`.** This item replaces the tuning, so the tool it replaces
  becomes used by nothing but its own tests. `AGENTS.md` says to consult the developer
  before removing something used only in tests, so it is left standing and the removal is
  asked on the pull request -- the same call `surfaces-from-world` made about the
  widest-or-highest face and `holes-fitted-like-pieces` made about `CrossSectionClassifier`.

### Verification

Tests first, at three levels, so each failure names its own cause:

- **The plane measurement on its own**: a synthetic depth image of a plane at a known
  height, with clutter standing off it, recovers that height and the plane's extent; a
  frame holding no dominant plane raises rather than answering a rectangle.
- **The rules on their own**: a surface described as a mirror-finished, colourless plane of
  about the modelled size is answered by the measurement; one the world describes with
  nothing falls back to the model; and a rule added while the tree is in use changes what
  the next surface is answered by -- the behavioural test #231's round settled is what says
  a tree is a tree.
- **The captures, which is the measurement that matters**: the measured table region is
  strictly inside `WIDEST_WORKSPACE`, it holds every detection the pipeline reports on all
  six, and the six report the same detections measured as tuned. The extents are read from
  the pipeline's own run rather than retyped from the figures above, so the assertion stays
  answerable rather than being a second copy of them.

Cost as a ratio to a same-run baseline, never in seconds against the node's 0.5 s period --
what #232 recorded about this container's speed moving between runs by more than the
difference being measured.

### The environment, and the bootstrap fault for the seventh time

Run under what six consecutive items have recorded: the `uv` on `PATH` is 0.8.17 and cannot
parse this repository's `pyproject.toml`, `pip install -U uv` puts a working one at
`/usr/local/bin/uv`, and `black` and `docformatter` go in by hand with `.venv/bin` on
`PATH` before `scripts/format_docstrings.py` will run.

`.claude/hooks/plan_item_bootstrap.py open` failed inside `save-plan.sh` exactly as #231,
#236, #238, #239 and #246 recorded -- the four-space item-field indentation against this
plan's two -- so `plan.yaml` was edited directly again. Seven rounds have now worked around
one unfixed script.

### `imagination-world-rejects-what-a-predicate-refuses`: what it took, and the fault that was not a refusal

Built 2026-09-03 in `auto` mode as pull request #255, off #238 for the reason the plan
above records.

#### The refusal had a quieter half

The item was raised about a relation the backend *refuses*. Reading
`_check_what_was_found` rather than the note turned up a second shape of the same fault, and
it is the worse one: a relation stated about the thing sought **alone** -- *supporting
something*, *stable* -- was never refused at all. It fell through to the residual filter and
was evaluated natively, where it reached for `_world` on a dataclass and raised
`AttributeError`. A refusal at least says what it cannot do. Both halves are closed by the
same thing, which is the detection having a body behind it.

#### One change in krrood, and it is about what a description leaves behind

The refusal is `condition._constrained_variables_ - {expression.variable}` being non-empty.
The things a statement *describes* are already resolved out of the world before the look, so
they are not variables the look has to answer -- subtracting them from that difference is
the whole change. What it needs beside it is that a described variable stops ranging over
everything it could have meant: `_hold_each_description_to_its_answer` pins each to the one
answer that resolved it, or the residual check would pass against something the statement
ruled out.

`PerceptionBackend.discard` is the other half: what the statement rejected, which a backend
that brought its findings into a world of its own takes back out. It does nothing by default,
because a backend that brought them nowhere has nothing to let go of.

#### A statement names the world's entity, and the copy answers for it

The one thing this design could not decide from the sources: a statement names a body of the
world the robot has, while the found things stand in the copy. Measured rather than assumed
-- `InContactWith(<a body of the copy>, <the original's own body>)` answers exactly as it does
against the copy's counterpart, positive and negative both, because the collision detector
resolves the second body inside the first one's world. So no substitution is needed at the
call site, and a statement is written the way it always was.

#### `Role[T]` decides where the spawn happens

`role_taker` is required at construction, so the piece has to exist in a world *before* the
detection does -- which puts the spawn inside `LoosePieceDetector._piece_at`, at the moment a
piece is recognised, rather than anywhere later. `ImaginedWorld` therefore replaces
`reference_frame` in that detector's signature rather than joining it: it carries the frame
the look reports in, so the parameter count is unchanged and there is one thing that knows
where a finding comes to stand. `MontessoriPerceptionPipeline.imagine()` is the one place a
look's world is made.

A finding's pose keeps naming the frame of the world the look was taken in; only the body
hangs from the copy's own counterpart, found by the name they share. Nothing a caller reads
off a detection changed.

#### Verification, and a container that cannot run the experiments suite

`test/krrood_test/test_eql/`: **1326 passed**, 3 skipped, against **1324** on the base tip in
a worktree with its own `*/src` on `PYTHONPATH`. The Montessori modules of
`test/experiments_test/`: **321 passed**, 1 skipped, 11 xfailed, against **310** on the same
base -- the eleven added and nothing else moved.

The three behaviours are mutation-checked: reverting the krrood refusal change fails the
end-to-end described-operand test, and stubbing out `discard` fails the discard test, neither
touching anything else.

**This container has no ROS at all**, which is new on this plan: `test/experiments_test/conftest.py`
imports `rclpy` and, through `coraplex`, `geometry_msgs`, so the directory cannot be collected
here, and `scripts/regenerate_all_orm.py` fails in giskardpy's own generator
(`CouldNotResolveType: DebugExpressionPublisher`) for the same reason -- both before this
branch changed anything. The Montessori test modules were run against the same sources from
outside that conftest, identically on this branch and on its base, which is what makes the two
numbers comparable. A ROS container runs them the ordinary way.

#### The bootstrap script's fault is unfixed, for the seventh round

`plan_item_bootstrap.py open` fails through `save-plan.sh` again, so `plan.yaml` and
`roadmap.md` were written directly and pushed with `save-plan.sh`.

### `expectations-from-events`: what it took, and the fault a stated reach exposed

Built 2026-09-03 as pull request #257, over the merge of #232, #222 and #246. 29 new
tests in `test_montessori_expectations.py` and `test_montessori_piece_matching.py`.

**The plan held, and the type it needed was the one it predicted.** An expectation is a
named piece, a `BelievedPlace`, what it should be resting on and what put the belief
there; `Expectations` keeps one per piece the robot has acted on; `SceneRequest` carries
what the asker believes, which is the change this plan's own note of 2026-08-31 said
this item would need. The three propagation rules are the item's notes verbatim, and the
one that carries the weight is written as its own test:
`test_a_belief_only_decays_when_something_acts_on_that_piece`.

#### Where a look is aimed and what it should rest on are two things

The single design call this item made, and it is what makes the failure story work.
`BelievedPlace.surface` is the plane a look searches; `Expectation.resting_on` is what
the piece should have come to rest against. A cube an insertion put through a hole is
looked for **on the lid** and expected to rest **on the hole**, and it is exactly that
gap which makes a cube left lying on the lid a reportable failure rather than a
sighting. Conflating the two would have made the item's own sentence -- *"the insertion
promised the cube would end up in the hole, and it is found resting on the lid"* --
inexpressible.

#### The five events are a mapping, not a chain of type tests

`SUPPORT_AFTER_EVENT` says what supports a piece after each kind of event: four name
what it has come to rest against and the fifth names what it has come off. Every other
kind says nothing about support, so a piece it names keeps its belief -- which is a rule
only its own test observes, exactly the shape #246 recorded about `advances_the_clock`,
so it was written rather than trusted.

#### The release spread has no default, and that is the honest answer

How far a released piece may land from the hole depends on the height it was let go from
and what it fell onto. There is no number here to derive, so `release_spread` is
`field(kw_only=True)` with no default and whoever declares the effect states it -- the
same call #238 recorded for `Near.radius` (*"how near is near is the caller's to say"*).

#### The fault a stated reach exposed, which is worth more than the feature

**This is the first belief on the plan that states its own reach.** Every belief before
it reached exactly `SEED_REACH`, so nothing ever varied a radius -- and varying one
showed the fit is *not monotonic in the reach*. `PieceMatcher._sweep` laid its grid out
as `arange(-radius, ...)`, whose phase therefore moves with the reach, so a peak one
reach lands on the next steps over. Measured on `displaced_cube_from_hole`: the cube is
fitted at a reach of 20 mm and of 40 mm and not at 24 mm or 30 mm.

That is #238's lattice finding in the sweep instead of the rectification, with the same
giveaway, and `offsets_within` fixes it: count outwards from the centre, so widening a
reach only *adds* placements. Writing the reach's other half as a test -- that a grid
stops inside the reach, since a belief says a thing is no further than that from the
place it names -- is what caught an overshoot the first version of the fix introduced.

Worth generalizing alongside #238's: **anything laid out from the edge of its own extent
is re-phased by every change to that extent**, and the cheap way to find out is to vary
the extent and check the answer is flat rather than merely plausible.

#### The lid marks do not come off, and the measurement says why

Two of the four captures `test_every_piece_resting_on_the_lid_is_found` still fails on
are a cube an insertion put at a named hole, so a history does say where to look, and
armed with one the cube **is** fitted. It is not fitted at every reach, and the grid fix
above is not the whole cause: with the grid monotone, `displaced_cube_from_hole` still
finds the cube at 20 mm and 40 mm and not at 24 mm or 30 mm, because the agreement
landscape over the lid is flat enough that which peak the coarse pass settles on decides
it -- the cube reaches 0.645 against a ghost cylinder's 0.641 at the same place, four
parts in a thousand, which is the same fragility #236 recorded at nine.

**So no reach was stated that takes the marks off.** Picking one that happens to work is
the tuning this plan has refused three times, and separating a piece from a ghost that
follows the same edges is `competing-explanations`' whole claim. The marks stay, and
what changed is what they record: `LID_PIECES_STILL_MISSED` now says that a history does
reach two of the four and what stops them, and names `competing-explanations` rather
than this item. The other two are pieces nothing acted on, so no history says anything
about them and a capture carries no world to say it instead.

That is a narrower delivery than the item's own note implies, and it is deliberate: the
mechanism is what this item claims, it is demonstrated end to end on the rendered scene
by `test_a_piece_a_colour_cannot_separate_is_found_because_an_action_promised_it`, and
the capture recall was always `competing-explanations`' to finish.

#### `InsertMontessoriShapeAction` is not edited, because it cannot be

`git ls-tree` finds it on `tracy_icra` and on no branch this item can base on, and
`ActionDescription` on `main` declares its effect as a `post_condition` returning a
symbolic expression with no per-action effect to read. So the declared effect is
`Expectations.released_over`, which whoever performs the action calls, and the wiring
lands on the demo branch -- the same split the perception node already has.

#### Open, and stated on the pull request rather than decided quietly

Whether the belief store belongs in `experiments` or, generally, in `krrood` or
`semantic_digital_twin`. Review overturned that placement twice on #222. `BelievedPlace`
lives in `experiments` because #232 put it there, and moving it now is a rename across
#232, #236, #238 and #239 -- the cost #238 refused for the `DetectedMontessoriShape`
rename.

#### Landing hazards

#255 renames `MontessoriShapeDetection` to `DetectedMontessoriShape` across
`pipeline.py`, `detections.py` and `occupancy.py`; this branch edits `pipeline.py` and
`piece_matcher.py`, so it inherits that rename the way #232 and #236 do. #223's
`Footprint` rename and #231's `EdgeFitDetector` rename conflict the usual mechanical
way. `offsets_within` is a new function in `piece_matcher.py`, which #231 and #239 both
edit.

### `surfaces-found-by-looking`: what it took, and the tuning that stopped mattering

Built 2026-09-03 as pull request #259, one commit off #231's tip. 39 new tests; **429
passed, 1 skipped, 16 xfailed** across `test/experiments_test/` against **390 passed, 1
skipped, 16 xfailed** on the parent in the same container, which is the 39 added here and
nothing else moved. Six modules do not collect either side, needing ROS or `rosbag2_py`,
as #238 recorded. Nothing outside `experiments/` is touched.

#### The claim, measured: the tuning no longer decides what is searched

The searched stretch of table falls from the **0.635 m²** a person had dragged the
sliders to, to about **0.51 m²** -- and starting from the whole **1.2 m²** the camera
looks over reaches the *same answer*, on every one of the six captures. That is the item
in one measurement: what is searched stopped being a number somebody typed and became
what the camera shows.

| capture | measured stretch | from the tuned workspace | from the untuned one |
| --- | --- | --- | --- |
| disoriented_cube_on_hole | x 0.357..0.915, y -0.450..0.483 | 0.521 m² | identical |
| displaced_cube_from_hole | x 0.352..0.914, y -0.450..0.464 | 0.514 m² | identical |
| non_inserted_objects | x 0.362..0.908, y -0.450..0.469 | 0.502 m² | identical |
| objects_on_montessori | x 0.355..0.915, y -0.450..0.473 | 0.517 m² | identical |
| stuck_cube_in_hole | x 0.369..0.911, y -0.450..0.482 | 0.505 m² | identical |
| tracy_pickup_demo | x 0.353..0.914, y -0.450..0.472 | 0.517 m² | identical |

The y minimum sits at the modelled bound in all six: the table reaches at least that far,
and the measurement will not report ground the world has not already allowed.

#### Only the extent is measured, and the first version measured too much

The plan said "a plane fit", and the first build fitted the height as well, answering
0.8804 to 0.8811 m against the modelled 0.88. That is a *better* reading of where the
table is and it was still wrong to ship: it moved the rectification plane, so **every**
detection on **every** capture moved with it -- up to 3.4 mm and 0.19 agreement -- for a
gain nothing had asked for. Two recorded facts settle it. This roadmap already says the
demo drifted away from its model in *layout* "though the table's height agreed exactly",
so the height is the half of the model that is not in question; and the lid's plane is
`TABLE_HEIGHT + BOARD_SCALE.z`, so measuring the table's height and not the lid's would
leave the two surfaces describing different tables.

With only the extent measured, **five of the six captures report exactly what the parent
reported** -- category, surface, position to the micrometre and agreement. Worth
generalizing: *a measurement that is more accurate than the thing it feeds is still a
change to that thing*, and the question is which half of the model is actually wrong.

#### The sixth capture, and a fit that was already two-valued

`stuck_cube_in_hole` moves one rectangular prism by 0.15 mm and from 0.826 to 0.806
agreement. Running #238's own diagnostic -- vary the crop and check the answer is flat --
says this is not the lattice: with the *modelled* finder throughout and only the region's
corner moved by whole pixels, the same prism flips between exactly those two readings,
non-monotonically in the size of the crop. So the two-valued fit is on the parent and this
branch merely reaches the other value once. It is the fragility #238 recorded and left to
`competing-explanations`.

The lattice itself is exact and is now asserted rather than hoped for: each measured
corner is a whole number of the modelled region's pixels from the modelled corner (7, 2,
12, 5, 19 and 3 across the six), which is #238's rule -- *anything that re-frames a
rectification has to land on the same lattice* -- pinned by construction.

#### What a finder needs is not only what the world says

#231's rendered-scene fixture annotates its table `SurfaceFinish.MIRROR`, and it draws
**no depth at all** -- 0 of 2,073,600 pixels. So the first build made a colour-only
pipeline unable to look at a mirror-finished table, raising where it used to answer.

The fix is not a fallback in the rules; it is that the finder says so itself.
`SoughtSurface` carries what one *look* offers as well as what the world states, and the
measurement's capability is now support-for-a-bound **and** depth having been returned.
That makes the capability genuinely load-bearing -- #231's own point that "a capability is
not a weaker rule, it is the half that says what a detector is *for*" -- and it fixed the
sibling's fixture without touching it. Worth keeping: **a description is not a capability;
what the picture offers is half of one.**

#### What it costs, and where the cost went

`detect` runs at **1.07x** the parent over the six captures, measured as a ratio to a
same-run baseline interleaved three times, per what #232 recorded about this container's
speed. The measurement itself is 0.061 s/frame; the narrowed passes pay most of it back.

The first version read all 2.07 M pixels of the depth image and cost 0.100 s/frame, for
1.24x. A surface cannot have been seen anywhere the world does not allow it to be, so only
the pixels its own space covers are read -- its stretch of plane, as thick as such a
surface's points scatter -- through the `outline_in` machinery `WorkspaceBox` already had.
`clip` is now written in terms of the same window rather than repeating the crop.

`SURFACE_SCATTER` is 17 mm, which is not chosen: it is the scatter the point-cloud trial
this package's detectors were written after measured on the bare steel.

#### Deliberately not built, each recorded rather than dropped

- **Clustering the surface's points.** The item's description names "the biggest such
  surface in view", and the bounding box of the banded points inside the modelled bound
  already shrinks to the table on all six captures, so nothing here needed the clustering
  and none was written. The measurement above is what says so.
- **A colour for the recorded table.** `None` means *not stated*, which is #216's own
  rule, and nothing here measured Tracy's table's grey. #239 states it, and its finish,
  on the twin's own surfaces; this branch states only the finish, and only for the
  recordings, which carry no world to state anything in.
- **Removing `tune_workspace`.** It is now used by nothing but its own tests. `AGENTS.md`
  says to consult the developer before removing something used only in tests, so it is
  left standing and the removal is asked on the pull request -- the same call
  `surfaces-from-world` made about the widest-or-highest face and `holes-fitted-like-pieces`
  made about `CrossSectionClassifier`.

#### Two API changes, both updating their own tests

`MontessoriPerceptionPipeline.rectify` takes the surface rather than a bare height, and
`searched_surfaces` takes the table it searches, because both used to read `self.table`
and the table a look searches is now the one that look found. `SceneWindows` draws the
table it looked at, so the clipped windows show what was searched rather than what was
modelled.

#### The environment

The easiest this plan has recorded, after #246's: `pip install -U uv` puts 0.12.9 at
`/usr/local/bin/uv` and `uv sync --extra dev --python 3.12` builds the whole workspace.
`black` and `docformatter` go in by hand with `.venv/bin` on `PATH`. The parent baseline
was taken in a worktree with its own `*/src` on `PYTHONPATH` and `experiments.__file__`
checked before it was trusted, per what #222 recorded about nearly measuring a branch
against itself.

## `how-to-look-concluded-from-the-request`: the last hand-wired step, and the tree that concludes it

Kicked off 2026-09-04 in `auto` mode, as pull request #266 off
`claude/knowledge-directed-perception-detector-zrm57t` (#239, open and out of draft, so
ready to stack on -- `check_dependency_readiness.py` reports `open_ready` for both this
item's dependencies, #231 and #239). #239 is the base rather than #231 because it is the
branch that already merges #159 in, which is what this item's own note says it stacks on
and reaches through. The session's branch arrived cut from `integration` -- the hazard
#199 exists to refuse, and the tenth time on this plan after #223, #225, #227, #232,
#236, #238, #239, #246 and #257 -- and was re-cut onto #239's tip before the first
commit.

The mechanical scope check reports every path this touches absent from `main` and shared
with #231, #238, #239, #257 and #259, which every round on this plan has already recorded
as expected: every file in this plan is introduced by #202, so path overlap alone would
fold the whole plan into one item. The purpose check decides it and comes back clean.
#231 concludes *which detector* answers a look at one piece on one surface; #239
concludes the *numbers* that detector reads the picture with; #238 clips the picture a
stated relation allows. None of them concludes *which detectors run over which surfaces
for a whole request*, which is what remains once their edits are removed.

### What was measured before anything was designed

`MontessoriPerceptionPipeline.detect` is where the residue actually sits, and it is two
hand-written steps rather than one:

- **The board detector always runs**, whatever was asked for. The method's own docstring
  says so -- *"The board is found whatever was asked for"* -- and it is true even of a
  request that admits only a shape detection.
- **The pieces are searched exactly one way**: `searched_surfaces` builds `[table, lid]`
  from a written `if board is None`, filters it by the request, and every surface that
  survives is handed to #231's rules for every one of `KNOWN_PIECES`.

That is the branch the developer's *"this feels rigid and hard designed and coded"* names.
Nothing about it is knowledge; it is a procedure written once and read every look.

### What is built

- **`RequestedLook`** -- what a rule reads about one request. Follows `TargetOnSurface`'s
  own rule exactly: everything a rule reads is stated on the case as a plain property, so
  a condition is an equality over a field rather than a reach into a `Type` object. It
  states whether a shape detection can answer the request, whether the board or one of
  its holes can, and whether the statement named a surface.
- **`WayOfLooking`** -- one interface, with the members today's `detect` already implies:
  finding the board and its holes, finding the pieces on each surface the request asks
  about, and finding everything. The composite is what an unnarrowed request concludes,
  so a single-class tree can answer a request that wants both without a fourth kind of
  conclusion.
- **`LookRules`** -- an `EQLSingleClassRDR` over `RequestedLook`, concluding a
  `WayOfLooking`, authored by fitting the three known kinds of request through a scripted
  expert, and readable by `render_tree`. The engine's `query` is `field(init=False)`, so
  fitting *is* the authoring model rather than a concession -- the same reading #239's
  section already recorded, and the path
  `tune-detection-rules-against-the-camera` extends.
- **`MontessoriPerceptionPipeline` loses its two hand-wired fields.** `board_detector`
  and `detector_rules` move onto the ways of looking that use them, and the pipeline
  carries one `look_rules` instead. Six fields become five, and the two the item's own
  note calls *"genuinely hand-wired"* become rule-concluded.

### Why the ways of looking, and not a list of passes

A single-class RDR concludes one value per case, and the conclusion has to be stateable
once when the rules are built -- a rule cannot conclude a list of passes over surfaces
that only exist once a frame has been looked at. So the tree concludes *how* the look is
taken and the way of looking derives its own passes from the scene, which is the same
move #231 made when its tree concluded a `PieceDetector` rather than a name.

### The demonstration of extensibility

#231 answered *"extensibility with new situations through interaction with an expert"*
only for the choice of detector, and its round left open that nothing yet asks an expert
when no rule fires, since the expert interface was not on its base. It is on this one.
A test fits a kind of request no rule covers and asserts the next look is answered the way
the expert said -- and, as #231's own `add_rule` test does, it fails if the tree is
rebuilt per look rather than grown in place.

### Deliberately not built here, each recorded rather than dropped

- **`headroom`.** The item's note assigns it to #239 -- *"`headroom` is
  detector-parameters-from-knowledge's to conclude"* -- and #239's own section records
  `DetectionParameters` as still to build on that branch. Concluding it here would build
  that item's value object on a branch it cannot see, which is the duplication these notes
  record five times over.
- **Skipping the board pass for a request about pieces.** It is the obvious saving and it
  would be wrong: `searched_surfaces` uses the board detection as the lid's boundary and
  as what stands on the table, so a look that skips it attributes a piece on the lid to
  the table. The rules state what the code already does; they do not invent a shortcut
  nobody measured.
- **Which pieces are candidates.** Narrowing `KNOWN_PIECES` from the request is
  #239's widening (*"which pieces are candidates at all"*), and #232 already moved the
  seeded half of it onto the belief.

### Landing hazards

`board_detector` and `detector_rules` move off `MontessoriPerceptionPipeline`, so any
branch constructing a pipeline with either keyword conflicts. #232, #236, #238 and #259
all edit `pipeline.py` on the other stack; whichever meets this branch first pays for it.
#223's `Footprint` -> `RectifiedFootprint` rename conflicts the same mechanical way it
does with every branch this plan has opened.

### The bootstrap script's indentation fault is still unfixed, for the eighth time

`.claude/hooks/plan_item_bootstrap.py` writes item fields at four-space indentation while
this plan's `plan.yaml` indents them by two, so `open` failed inside `save-plan.sh` --
`save-plan.sh` exits 1 on *"No changes to save"*, which is exactly what a rewrite that
matched nothing produces. Worked around an eighth time by editing `plan.yaml` directly.
It is the same family as #160 and still wants its own bug-fix pull request.

### The tracking-issue subscription could not be armed

`subscribe_pr_activity` on issue 201 was refused by this session's permission classifier,
the same way #257's round recorded it. The kickoff carried on, as
`plan-item-gathering.md` says to: subscribing is a convenience for noticing concurrent
structural changes, not a precondition for anything here.

### `how-to-look-concluded-from-the-request`: what it took, and the rule that cannot be written down

Built 2026-09-04 as pull request #266, one commit off #239's tip. 15 new tests; **412
passed, 1 skipped, 16 xfailed** across `test/experiments_test/` against **397 passed, 1
skipped, 16 xfailed** on the parent, taken in a worktree with its own `*/src` on
`PYTHONPATH` and `experiments.__file__` checked before it was trusted, per what #222
recorded about nearly measuring a branch against itself. That is the fifteen added here
and nothing else moved. Six modules do not collect either side, needing ROS or
`rosbag2_py`, exactly as #238 and #259 recorded. Nothing outside `experiments/` is
touched.

**The plan held, and the two ways of looking were the two the code already implied.**
`FindTheBoard` and `FindThePieces`, each stating the requests it answers as an entity
query language condition; `LookRules` an `EQLSingleClassRDR` over `RequestedLook`
concluding one of them; `MontessoriPerceptionPipeline` down from six fields to five,
with `board_detector` and `detector_rules` moved onto the ways that use them and sharing
the one board search so a look reporting both runs it once.

#### A rule that concludes a collaborator cannot be written down

**The finding worth more than the feature, and it is a constraint on the engine rather
than on this item.** `EQLSingleClassRDR` persists its model whenever a fit finishes --
`_saved_when_the_fit_ends` runs on the way out either way, which is the feature that
keeps the rules an interrupted fit had authored. It writes them as *Python source*, and
`serialization.py`'s value serializer spells an `Enum` member, a `bool`, a number, a
string or `None`. Nothing else. So every one of the ten tests that built the rules failed
with `UnsupportedNodeForSerialization: Cannot serialize node of type 'FindThePieces'`.

The conclusion here is deliberately the way of looking *itself* rather than a name for
one -- which is #231's own call, made for the same reason ("the rule tree concludes the
pipeline's own detector *instances* rather than constructing fresh ones"), and what lets
each way bring its own condition instead of a table mapping names to objects. So
`NullModelSaver` states plainly that these rules are not persisted: they are authored in
code from the ways themselves, and building the rules again is what recovers them.

**Worth knowing for `detector-parameters-from-knowledge`**, whose own section plans "an
`EQLSingleClassRDR` over #231's `TargetOnSurface`, concluding a `DetectionParameters`,
rendered by `render_tree`". A `DetectionParameters` is a dataclass of numbers, not one of
the five kinds the serializer spells, so that item meets this wall too and has the same
two ways out: a null saver, or a conclusion the serializer can write.

#### A capability that claims too much is refused when the rules are built

Found by mutation-checking rather than by reading. Making `FindTheBoard.capability`
return `pieces_are_asked_for` -- so both ways claim the same requests -- does not produce
a wrong answer at look time: the fit itself stops converging and every test that builds
the rules errors. That is the engine refusing to author a tree it cannot make agree with
the cases it was given, and it makes a capability load-bearing here in the same sense
#231 recorded it ("a capability is not a weaker rule, it is the half that says what a
detector is *for*").

It is recorded rather than pinned by a test: what it pins is the engine's convergence
rule, not this item's claim.

#### What the three mutation checks caught

Each fails its own test and nothing else, following what #246 and #257 recorded about a
refactor's tests being worth what they would catch:

- rebuilding the tree where it is read fails only
  `test_a_way_of_looking_added_at_runtime_answers_the_next_request_of_that_kind` -- the
  same shape #231's own `add_rule` test has, and the property its review round settled is
  what makes a rule tree a rule tree;
- a hole not counting as asking for the board fails only
  `test_a_request_for_the_holes_asks_for_the_board_that_carries_them`;
- the capability mutation above, which is caught loudly rather than by one test.

#### Two API changes, both updating their own tests

`RectifiedFrame` moved from `pipeline.py` to `look_choice.py`, beside the `SceneToSearch`
that is now its only reader, and `searched_surfaces` moved from the pipeline onto that
scene, since it reads the surfaces and the request and nothing else. Three tests reached
the detector rules through the pipeline and now read them off the way of looking; two
read the surface search off the scene the pipeline builds for a look. That is the same
kind of change #238 and #259 each recorded, and no test's assertion changed.

#### The board is still found whatever was asked for

`FindThePieces` finds the board before it searches anything, because how far each surface
reaches is read from the board as it was *seen* -- the split #221 made and #225, #238 and
#259 each kept -- and reports it, since this look measured it. That is what `detect`
already did ("the board is found whatever was asked for"), so the rules restate the
existing behaviour rather than changing it, which is why five of the six captures and
every rendered-scene test read exactly as before.

#### The environment, which is the easiest this plan has recorded

The `uv` on `PATH` is 0.8.17 and cannot parse this repository's `pyproject.toml`, as
seven consecutive items have recorded; `pip install -U uv` puts 0.12.9 at
`/usr/local/bin/uv` and `uv sync --extra dev --python 3.12` builds the whole workspace
first time. `black` and `docformatter` go in by hand with `.venv/bin` on `PATH` before
`scripts/format_docstrings.py` will run.

`.claude/hooks/plan_item_bootstrap.py open` failed inside `save-plan.sh` for the eighth
round, the four-space `ITEM_FIELD_INDENT` against this plan's two-space item fields,
exactly as #231, #236, #238, #239, #246, #255 and #257 recorded. The failure is quieter
than those rounds described: `save-plan.sh` exits 1 on *"No changes to save"*, which is
what a rewrite that matched nothing produces, so the error the script swallows is not an
invalid-YAML error at all. Worked around an eighth time by editing `plan.yaml` directly.

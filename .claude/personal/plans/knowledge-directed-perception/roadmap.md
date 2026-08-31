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

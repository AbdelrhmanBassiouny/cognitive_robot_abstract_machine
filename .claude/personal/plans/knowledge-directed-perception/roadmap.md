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

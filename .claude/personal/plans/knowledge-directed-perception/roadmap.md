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

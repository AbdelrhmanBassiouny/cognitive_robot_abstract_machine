# Knowledge-directed perception: scene grounding

This plan is one of three successors to `knowledge-directed-perception`, split on
2026-09-05 because the source plan grew to 29 items and 8,146 combined lines - past the
`plan-size-limits` budget (15 items / 2,000 combined lines per plan) by a wide margin. The
split is recorded in full on `plan-size-limits`'s roadmap and on tracking issue #200. The
three successors are `knowledge-directed-grounding` (this plan), `knowledge-directed-
requests` and `knowledge-directed-expectation`, one per wave of the source plan; all three
keep `tracking_issue: 201`, reusing the source plan's mailbox. The full predecessor
roadmap (6,492 lines) is not reproduced here - it stays reachable in the personal-notes
branch's history immediately before the split commit. What follows is compressed to what
still binds future work; per-round implementation narrative about already-built items is
compressed into each item's own `notes` in `plan.yaml`.

## Why this plan exists: the claim, and where grounding starts

The claim the whole programme supports: a robot that knows what it is looking at, what
supports it, what it just did to it and what it is about to do perceives better than one
that does not - and the cognitive architecture is what makes that knowledge reach
perception at all. The demo is the Montessori shape-sorting board on Tracy's brushed steel
table.

Three faults observed on the running node on 2026-08-28 are one fault: the scene is
described to perception by constants instead of read from the world the node already
fetches.

1. **The workspace clip shows the floor.** `TRACY_WORKSPACE` is a hand-written rectangle
   that reaches past the table; `table_top_z()` already reads the tabletop's collision
   shape for its height and discards the scale and origin that are exactly the bounds
   being guessed.
2. **A piece resting on the board's lid is never found**, because the pipeline rectifies
   loose pieces onto exactly one plane and codes the board as an obstacle to exclude
   rather than a supporting surface.
3. **Duplicate detections ride the board's borders**, because nothing checks whether a
   contour's centre falls *on* the board's edge, and nothing forbids two detections
   occupying one place.

This plan fixes all three by removing the constants rather than patching each symptom.

## Why not build this inside RoboKudo

Decided 2026-08-28 with the developer: own reasoning layer, detectors behind an
interface, a RoboKudo analysis engine as one of those detectors later (`robokudo-
detector`, in `knowledge-directed-expectation`, deliberately last and droppable).
RoboKudo's knowledge coupling is one-way (pushes hypotheses into the twin, nothing reads
the twin to decide what the tree does) and its request interface is a flat designator
over a ROS action - replacing it with the entity query language is replacing its front
door, not extending it. Our side already has the typed data structures and krrood's
`Query`, an inspectable expression tree with an extensible backend protocol.

## Why perception is a backend, not a parser

Revised 2026-08-28 at the developer's suggestion: `krrood.entity_query_language.
backends.QueryBackend` is an established ABC (`SelectiveBackend`/`GenerativeBackend`,
four implementations), and `SQLAlchemyBackend` already does "translate the query into
another engine's plan and execute it there" - a perception backend is the same move
against a camera. Conditions are split, never ignored: pushed-down conditions shape the
search, everything else is a residual filter over what came back, and a condition that
fits neither raises. The backend declares how it reads (`Directive.LOOK_FOR`), so a query
answered by looking verbalizes as "Look for ..." rather than "Find ...". Built in
`perception-backend`, `knowledge-directed-requests`.

## The three waves, and what each successor plan is

- **Grounding** (this plan) removes the constants: the workspace and every plane height
  come from the world; every supporting surface gets its own detection pass; a detection
  may not sit inside a body already known, nor on top of another detection.
- **Requests** (`knowledge-directed-requests`) makes asking and looking the same act: the
  perception backend, the surface-finish annotation, and the rule tree that chooses a
  detector and its parameters. `choose-detection-method` is the item the paper's central
  claim rests on.
- **Expectation** (`knowledge-directed-expectation`) closes the loop: Segmind's support
  events and an action's declared effects arm what perception expects, and a look that
  finds nothing (or something else) there is a detectable, reportable failure.

## The deliverable is the demo, not the pull requests

**Standing rule, shared by all three successors:** an item's branch merges into
`tracy_icra` as soon as it works, without waiting for its own pull request to land on
`main`. The pull request is the review record; `tracy_icra` is the running truth.
Coupling them would let review latency starve the demo. Each wave carries its own demo
item (`demo-runs-on-grounded-perception` here, `demo-asks-by-query` and `demo-detects-
and-recovers-a-failed-insert` in the other two) saying what has to be true on the real
robot before that wave counts as finished, in its own track so it runs alongside the
engineering rather than queuing behind it.

`demo-catches-up-with-main` (done, this plan) merged `main` into `tracy_icra` first,
while it was still cheap - every later item across all three plans is developed off
`main` and has to reach that branch.

**`depends_on` means stacked on, never waiting for a merge**, across all three
successors: every item of `montessori-eql-stack` is based on an unmerged parent, and this
works the same way, so a pull request awaiting review costs the demo nothing.

## The budget: 2026-09-15

Thirteen working days from 2026-08-28. **The cut comes from depth, not from pillars**:
every item across all three successors is load-bearing for the claim, so nothing is
dropped; each is built in the narrowest form that demonstrates its own claim. If the
deadline forces a further cut, protect `demo-detects-and-recovers-a-failed-insert`
(`knowledge-directed-expectation`) - the end-to-end story the paper is written around -
and drop `robokudo-detector` (`knowledge-directed-expectation`), which nothing else
depends on and no demo item needs.

## Sequencing decisions

- The perception package lands on `main` first (`montessori-perception-on-main`), since
  every item across all three successors edits files that exist on no branch but
  `tracy_icra`.
- The `surfaces` track (this plan) is sequential: each item edits the same pipeline the
  previous one left behind, so branches stack rather than run in parallel.
- `surface-finish-annotation` (`knowledge-directed-requests`) depends on nothing and can
  start immediately, off `main` - it touches only `semantic_digital_twin`.

## Relationship to `montessori-eql-stack`

Different initiative, same demo. That plan is about *asking* (the console, autocomplete,
replay); this one is about *answering by looking*. They meet at the backend: once
perception is a query backend, a question typed into that console can be answered by the
robot going and looking rather than only recalling what it already recorded.

## Landing hazard shared by every item in the `surfaces` track

`surfaces-from-world` (#205), `detect-per-supporting-surface` (#221) and `montessori-
classes-in-the-orm` (#223) all edit `pipeline.py` and `footprint.py`; #223 renames
`experiments.montessori.perception.footprint.Footprint` to `RectifiedFootprint` to resolve
an ORM name collision with `semantic_digital_twin`'s own `Footprint`. Every branch
stacked past #223 in the `surfaces` track conflicts on that rename; the resolution is
mechanical (take the incoming edit, spell the class `RectifiedFootprint`) and is recorded
here once rather than re-derived on each branch.

## Environment note, shared across all three successors

The repository's own conftest regenerates ORM interfaces on collection, which imports
`giskardpy` and needs a ROS 2 installation most containers lack - this reproduces on
unmodified `main` and is not any item's fault. `uv sync --extra dev --python 3.12` builds
the whole workspace, including `giskardpy` and `coraplex`, and is the environment every
item from `surface-finish-annotation` onward verified against; earlier items used a
hand-built recipe (a virtual environment, `random_events` built from source, `urdf_parser_py`
copied in) that `uv sync` supersedes.

# icra-mechanism: roadmap

One of three successors of `icra-experiments`, split 2026-09-05 for the plan
size budget (`plan-size-limits`, tracking issue #200) — the item limit alone
(33 > 15), not the line budget. The split is by wave, the plan's own
existing organizational seam: `icra-foundation` is the `foundation` wave,
`icra-mechanism` (this plan) is `mechanism`, `icra-evidence` is `evidence`.
All three keep `tracking_issue: 252`, the original mailbox. Full split
rationale and what it cost lives in `plan-size-limits/roadmap.md`'s "Done
2026-09-05: `split-icra-experiments`" section; the predecessor's full
roadmap is reachable in the personal-notes branch's history immediately
before the split commit.

**Almost every item in this plan depends on at least one item in
`icra-foundation` or `icra-evidence`** (eleven of this plan's fourteen items
carry a cross-plan `blockers` entry instead of a `depends_on` edge, since
`depends_on` cannot cross a plan boundary — see plan.yaml). Read `icra-foundation`'s roadmap
first for the programme's overall "why"; this file states only what is
specific to what this wave measures.

## Why this wave exists

**Restated 2026-09-08** — see `icra-foundation`'s roadmap for the full
restatement. This wave builds what makes the subsystems one system:
capability declaration in a single vocabulary and per-predicate routing
across backends that are interchangeable behind it (`backend-routing`), a
control program whose optimization constraints are queries over the same
representation and whose own state is queryable in the same language
(`control`), physics as one more answerer of the same predicates
(`backend-routing`), the snapshot working memory the agency questions rest on
(`backend-routing`), typed and predicted failure with the
ablations/perturbations that produce it on purpose (`failure`), and the
verbalised-memory/VLM baselines the experiments compare against
(`baselines`).

The original sentence, which most items here are still written against: the
same EQL query selects which backend answers each predicate, drives what the
robot perceives, and verifies the result in the digital twin; removing
knowledge produces failures the query predicts.

## Structural decisions taken at creation (2026-09-03)

- The two core mechanisms (per-predicate routing by declared capability, and
  the physics verification backend) live here, not in
  `knowledge-directed-perception`. That plan's
  `imagination-world-rejects-what-a-predicate-refuses` item is covered by
  `physics-verification-backend` in its narrow form and should be marked so
  there rather than built twice.
- Three lanes, one per person (see below); items in different lanes run in
  parallel, an item waits only on what `depends_on`/`blockers` names.

## Lane assignment (unchanged from the predecessor)

This wave's tracks split across all three of the original lanes:
`backend-routing` is lane 1 (robot, perception and mechanisms — the same
lane as `icra-foundation`'s `integration` track and `icra-evidence`'s
`experiment-b`); `failure` is lane 2 (experiment infrastructure and
long-term memory — with `icra-foundation`'s `scenario-model`/`long-term-memory`
and `icra-evidence`'s `experiment-c`/`experiment-d`); `baselines` is lane 3
(baselines, question set, figures and writing — with `icra-evidence`'s
`experiment-a`/`release`). The lane order for this wave's items:

**Lane 1** (from `icra-foundation`'s `integrated-simulation-pipeline` and
`simulated-camera-feeds-perception`): `backends-declare-their-capabilities`
→ `query-routed-per-predicate` → `physics-verification-backend` →
`snapshot-working-memory` → (`icra-foundation`'s
`tracy-demo-takes-the-integrated-branch`) → `icra-evidence`'s
`experiment-b-in-simulation`.

**Lane 2** (from `icra-foundation`'s `scenario-domain-model` and
`montessori-scenarios`): `failure-taxonomy-and-typing` →
`knowledge-ablations` → `perturbations` → `icra-foundation`'s
`episodes-queried-by-eql` → `failure-predicted-from-the-query` →
`icra-evidence`'s `experiment-c-in-simulation`. `expectation-checked-under-perturbation-in-simulation`
was added to this lane 2026-09-05 (see below).

**Lane 3** (from `icra-evidence`'s `question-set-and-ground-truth`):
`working-memory-verbalised` → `vlm-baseline-harness` → `icra-evidence`'s
`paper-figures-from-episodes`/`experiment-a-in-simulation`.

## The budget: 2026-09-15

Twelve days from 2026-09-03; the full table lives in `icra-foundation`'s
roadmap. This wave's state-reached milestone: **go/no-go Sunday evening
(Sat 5/Sun 6) — `query-routed-per-predicate` and `physics-verification-backend`
answer a mixed query in simulation.** If it fails, the memo's fallback
holds: submit with Experiments A and C and drop B's injection half. **Never
cut:** the temporal scenarios, the perturbation conditions, the hybrid VLM
baseline, the failure-prediction metric, the determinism runs.

## Cross-plan prerequisites relevant to this wave

- **knowledge-directed-perception**'s `expectations-from-events` is not
  started there and is the failure-detection story: it blocks
  `failure-taxonomy-and-typing`'s expectation-derived type (blocker already
  on that item, unchanged by this split) and `icra-evidence`'s
  `experiment-c-in-simulation`.
- **eql-verbalization**'s #33 carries the reviewed scene wordings
  `working-memory-verbalised` renders with; the item does not wait for #33
  to rebase or land onto #229. Two wording decisions on #33 are the
  developer's own.

## Open questions for the developer

- Which vision-language model and provider `vlm-baseline-harness` calls, and
  whether the credentials can be in CI (they need not be — the live test is
  skipped without them). `icra-evidence`'s Experiment D reuses this harness
  and adds a second part to the same question: how many episodes fit one
  context once video frames are sampled.
- Whether `knowledge-directed-perception`'s `expectations-from-events` is
  still needed for the paper once `snapshot-working-memory` and
  `failure-taxonomy-and-typing` exist, or whether the violated-expectation
  report folds into the failure typing here.

## 2026-09-05: the expectation mechanism gets its own simulated test

Raised by the developer on `knowledge-directed-perception`'s #257
(r3940274577): *"I want to test that with an actual robot plan execution in
simulation with perturbations, check if that is already in the
icra-experiments plan such that it tests this whole expectation process or
not, if not then we need to add it there."*

It was not. `perturbations` builds the perturbations and `icra-evidence`'s
`experiment-c-in-simulation` runs the insertion trial under every condition
and types every failure, but nothing between them asserted that the
*expectation* an insertion arms is contradicted in the relation the
perturbation actually breaks — a wrong expectation report would be typed and
counted rather than caught.

So `expectation-checked-under-perturbation-in-simulation` was added to the
`failure` track, depending on `perturbations` (this plan) and
`icra-foundation`'s `integrated-simulation-pipeline` (blocker). Its four
cases are the four outcomes the report can have: a piece pushed off the lid
after release contradicts `Near`/`InsideRegion`, a release that stops short
contradicts `InsideRegion` alone, a piece the gripper never released is
reported as nothing found, and an unperturbed run contradicts nothing. It is
also the first place the success case is checked against a look rather than
a stated sighting — on #257 that case is checked only against a stated
sighting, because a look reports a piece's height from the depth image with
a fallback that puts every unresolved piece standing on the plane it was
found in. Recorded here rather than on `knowledge-directed-perception`
because the test needs a pipeline that can run a plan, and that pipeline is
`icra-foundation`'s.

## 2026-09-08: the two halves the thesis named but the plan had no item for

Refocus pass across all three ICRA plans (the developer's direction is quoted
in `icra-foundation`'s roadmap). This wave gained the two items that carry
the integrative claim, and one existing item was moved off the critical path.

### `perception-backends-are-interchangeable` (new, `backend-routing`)

A vision-language and a visual-question-answering backend implement the same
interface the detector stack implements, take the same `RgbdFrame`, declare
capability in the same vocabulary and write the same bodies, poses and
relations into the twin — so the routing, the control program, the event
monitor, the episode record and the query language are all unchanged by the
swap. The plan already had the vision-language model as a *baseline*
(`vlm-baseline-harness`); it had nothing that made it a *backend*, which is
the stronger and more interesting claim, and the one that says what the
architecture is actually built on. The classical stack stays the default
because the cost comparison needs something whose cost is known.

### `control-constraints-and-degrees-of-freedom-queried` (new, its own `control` track)

The half of the thesis sentence with no item behind it. Its own track rather
than a fourth item in `backend-routing`, because control is a peer of
perception and memory in the claim, not a routing concern.

**Rewritten the same day, at the developer's correction.** The first version
had the statechart's constraints *built* from queries over the twin — the
goal pose, the hole geometry, reachability and the degree-of-freedom limits
each queried, and the giskardpy tasks assembled from the answers. That has
never been implemented here, it is a far larger task than the week holds, and
it is not what the claim needs. In the developer's words, what was meant was
*"just the ability to query the control system using predicates or methods or
the model itself, because it is all the same knowledge representation" —
"what is the constraint for inserting the cube vs the one for the triangle,
and it gives me a giskard constraint for that task as an answer, or what
degrees of freedom you made use of to execute the insertion task and what did
you fix or ignore".*

So the item is a **read**, and the representation is already there:

- `GiskardConstraint` is a dataclass — name, the constrained expression, its
  quadratic and linear weights, its normalization factor.
- `ConstraintCollection` holds a task's equality and inequality constraints,
  grouped by the enforcement strategy that turns them into rows of the
  quadratic program.
- Every `MotionStatechartNode` owns one; `NodeArtifacts.constraints` is the
  assembled shape.
- coraplex's executable holds the `MotionStatechart` a plan node ran.
- A constraint's expression answers `free_variables()`, which is what says
  which of the world's `DegreeOfFreedom` instances it actually touches.

What is missing is the reach and the naming: the collection and the statechart
are private attributes, the executable keeps only the motion currently
running rather than the one each plan node ran, and nothing names the degrees
of freedom a task constrains as against the ones it leaves free. Give those a
name and an EQL spelling and the control bucket is answered.

**One knock-on.** The old version claimed it was what made the
no-degree-of-freedom-limits ablation a knowledge condition rather than a code
branch. That claim did not need it: `DegreeOfFreedomLimits` already lives on
the twin's own `DegreeOfFreedom` and the controller reads it there, so the
ablation is a twin edit already. `knowledge-ablations` now says so.

### `physics-verification-backend` moved off the critical path

Kept, reframed and demoted. Its value in the restated thesis is that physics
is one more backend answering the same predicates from a different source —
not that verification is a headline mechanism of its own. It is now the first
thing cut if the week runs short, ahead of anything in the memory or control
tracks. The memo's original cut order put Experiment B's injection half
first; this is consistent with that, and makes it explicit at the item.

### Working memory, and why it has no Bloom level

`snapshot-working-memory` gained the note that it is where the agency
questions are answered. Because the twin follows the gripper's kinematics
while the robot acts and re-perceives only when something changed while it
was idle, the record distinguishes *a piece the robot moved* from *a piece
that moved on its own* — which is what "did it move, and did you move it"
asks, and what no single image can hold. Bloom's taxonomy has no level for
working memory; the developer's point is that this is a gap in the taxonomy
as an account of a robot rather than a gap in the system, and the paper
argues it rather than working around it. Recorded here because it is a claim
about this item's mechanism, not only about the question set.

## 2026-09-09: the fourth round on #298 lands here, as one item and one amendment

The developer's fourth review round on `icra-foundation`'s `simulated-camera-feeds-perception`
(#298) was not about that branch. Its four comments ask for `BoardDetector`'s stated defaults to be
derived rather than written down, for holes and perforated surfaces to become concepts at a meta
level, for a detector's capability to name *fields of classes* as entity-query-language `Attribute`s
or `MappedVariable`s rather than field-name strings, and for a look to be asked for by handing the
backend an underspecified `Match` that helpers fill out from what the model knows -- possibly as an
EQL-based ripple-down rule tree. The last comment asks for exactly this: *"Maybe all these can be
organized as plan items, Discuss with me the best course of action regarding that"*.

### What already exists, which is most of it

Checked in the merged tree rather than assumed, and it changes the size of the ask by more than half:

- **`PerceptionDetector.capability(look) -> ConditionType`** already states what a detector can
  answer *as an entity-query-language condition*, so that one statement both decides a look and
  becomes a rule in the tree choosing among the detectors that can answer it. A detector is never
  chosen for a look it declared it cannot answer.
- **`DetectorChoice` is already the EQL-based ripple-down rule tree** the round suggests --
  `krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR`, built from the underspecified
  statement *"a look whose detector is to be worked out"*, and live: `add_rule` grows it while it is
  in use.
- **`SceneRequest(Look)`** is already the underspecified description -- the kind of thing sought, the
  surface, the placement relations, the colour, each a narrowing rather than a promise.
- **`AttributeEqualityToLiteral.read_from`** already reads an equality about the selected variable's
  own attribute back out of a condition, which is the reading half of "EQL Attributes instead of a
  field string name".

All four arrived on #265 through #275 (`a-look-is-described-by-a-match`) and the ripple-down stack
(#77). So the architecture the round describes is the one this stack already chose, and writing four
items for it would have duplicated work already merged. That is the finding worth carrying: **check
the convergence's own merges before sizing anything that sounds like new perception machinery.**

### So it is one new item and one amendment, not four items

`holes-answered-as-predicates` is the genuinely new work: holes and perforated surfaces as predicates
any body can be asked about, the detector family that answers them (the colour-reading one and the
depth-reading one standing beside each other rather than as two branches inside `BoardDetector`), and
`BoardDetector` stating no number of its own once all five of its defaults are read off the board the
twin already holds.

`backends-declare-their-capabilities` takes the rest as an amendment rather than a second item,
because a capability naming a field of a class is that item's own subject at finer grain -- its notes
already say `QueryBackend` gains `capability()`, "the same shape #231 gave detectors". Added to it:
the field-level spelling, and the helper that fills an underspecified description out from what the
model knows about the class named in it.

**Why an amendment rather than the second item the developer picked.** `plan-size-limits`' budget is
15 items per plan, and this plan stood at 14; two new items would have made 16, breaching the cap
that `icra-experiments` was split into three plans to satisfy -- at real cost, days earlier. The
split is by what the work is rather than by the cap, and it happens to fit: one genuinely new
subject, one refinement of an item that already owns it. Reverting to two items is a one-line
manifest change if the cap is judged the lesser constraint.

The vision-language half of the round needs nothing new. `perception-backends-are-interchangeable`
already has a vision-language backend answering a look behind the same interface and into the same
twin, and `vlm-baseline-harness` builds the model arm; verbalising an underspecified description is
what those two read.

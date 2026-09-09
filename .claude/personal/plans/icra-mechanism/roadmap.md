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

## 2026-09-09: new work is cut off `tracy_icra`, and the readiness rule is retired

The developer's direction, on #298 and in his words: *"I want first to merge everything now fast into
265 and then into tracy_icra then merge any new features into tracy_icra directly and stop basing
them on main or on other tracks. Because I want to start recording episodes with perturbations in the
simulation as fast as possible."* Applied to all three ICRA plans on 2026-09-09 and recorded on
tracking issue #252.

**The sequence it sets.** Every in-flight branch merges into #265; #265 merges into `tracy_icra`;
from then on a new item is cut off `tracy_icra` and merges back into it. `tracy_icra` becomes the one
trunk this programme works on, which is what `tracy-demo-takes-the-integrated-branch` already said
about every later merge -- *"from then on every later merge into tracy_icra is a merge of the
integrated branch, never of individual stacks"* -- now brought forward and widened to new work as
well.

**What it retires.** The readiness rule -- an open, non-draft pull request counts as ready to build
on -- was the whole basis on which #278, #294, #296 and #298 each argued their base, and it exists to
let work stack before its parent lands. Cutting off a trunk instead removes the question: there is no
parent pull request to be ready or not. New items therefore record no `depends_on`-driven base
argument at all; they say `tracy_icra`.

**What it does not change.** No branch already in flight is repointed. Repointing is a merge rather
than a bookkeeping change, and every one of them is about to be merged into #265 regardless, so
moving their recorded bases now would cost conflicts to reach the same tree. Their roadmap entries
keep the bases they were actually cut from, which is what a later reader needs.

**One argument it settles retrospectively.** `montessori-scenarios` (#296) argued the day before, and
measured, that basing on #265 was the sideways merge the convergence pass had ruled out -- seven
branches merged *into* #265, never into each other, so as not to pay the same conflict set twice.
That reasoning stands for what it was, and stops applying here: the fast merge into #265 pays that
conflict set once, deliberately, and everything after it is cut off a trunk that already carries it.

**A tooling divergence, flagged rather than fixed.** `check_dependency_readiness.py` and the
dashboards still implement the readiness rule, so a new item cut off `tracy_icra` whose `depends_on`
names an item whose pull request is a draft will read as "not ready" when nothing is actually
blocking it. Nothing here changes that; it is worth a `plan-tracking-skills` item if the trunk
workflow outlives this deadline.

## 2026-09-09: `snapshot-working-memory` kicked off, based on #265 rather than `tracy_icra`

Kicked off by `/plan-item-kickoff icra-mechanism snapshot-working-memory`. #301.

### Base branch, decided against this item's own recorded blocker

The item's `blockers` entry named `icra-foundation`'s `simulated-camera-feeds-perception`
as `not_started`. Checked against `icra-foundation/plan.yaml` on kickoff: that item is
actually `done` (#298, merged into #265) — the blocker text was stale, written before the
2026-09-05 split. So the recorded dependency is not what is actually blocking this item.

What is: this same day's branching change (`icra-foundation/roadmap.md`, "new work is cut
off `tracy_icra`, and the readiness rule is retired") says every new item should now cut
off `tracy_icra` rather than argue a base by dependency readiness. Checked directly rather
than taken on trust: `tracy_icra` does **not** yet carry #265's content — `git merge-base
--is-ancestor origin/claude/icra-experiments-simulation-pipeline-w4ep7n origin/tracy_icra`
answers no, and a diff between the two branches is 630 files / 86,630 insertions, including
`results_recording.py`, the board detector and the whole perception stack this item needs.
The merge of #265 into `tracy_icra` is `tracy-demo-takes-the-integrated-branch`, still
`not_started` there, gated on the robot.

Put to the developer directly on this session; the answer was to base on #265. So this
item's branch (`claude/plan-item-kickoff-icra-snapshot-f69vef`, #301) is cut from
`claude/icra-experiments-simulation-pipeline-w4ep7n`, not from `tracy_icra` or `main`. It
will need restacking onto `tracy_icra` once `tracy-demo-takes-the-integrated-branch` lands
there — noted as a follow-up on this item rather than assumed away.

### What already exists, checked against #265's tree before designing anything new

Perception never commits a pose into the real twin today. `MontessoriPerceptionPipeline
.detect()` returns a `MontessoriScene` whose sightings stand in `MontessoriScene.imagined`,
a `deepcopy` (`ImaginedWorld.copied_from`) that is thrown away after a query is answered —
"nothing here ever reaches the world it was copied from" is the module's own docstring.
No `update_body_pose`/`commit` method exists anywhere, and nothing gates perception on
grasp state (there is nothing yet to gate). There is also no `is_executing`/idle flag on
`Context` or the executable, and no existing pose-noise/repeatability measurement.

Attachment is already the kinematic-following half this item's notes describe: `ReAttachNode`
reparents the grasped body onto the gripper's `tool_frame` via `world.move_branch` (pick-up)
and back onto `world.root` on release (placing) — a plain kinematic reparent, not a separate
boolean. `is_gripper_holding_something(gripper)` (`semantic_digital_twin/reasoning
/robot_predicates.py`) already answers "is anything attached" the cheap, exact way that
matches this reparenting scheme (kinematic-branch membership), rather than the ray-cast
`is_body_gripped` predicate built for a different purpose (detecting a grasp from geometry).
This item reuses `is_gripper_holding_something` as its idle/acting guard rather than adding
a new state flag.

The commit-a-pose-once-matched mechanism is not new either: two places in #265's tree
already write a state-only pose onto an *existing* body the same way —
`ImaginedWorld.spawn`'s own docstring ("a later look that finds the piece somewhere else
writes the new placement into the connection this one built") and, generically,
`coraplex/perception.py`'s `Detection.apply_to`, which resolves the matching annotation and
sets `body.parent_connection.origin = detected_global_pose` outside any `world.modify_world()`
block — placement is state, not structure. This item's commit step follows that same,
already-established pattern rather than inventing a second way to move a body.

### Matching a detection to an existing piece

Neither of the two commit precedents above solves multi-instance matching in general —
`Detection.apply_to` itself raises `AmbiguousDetection` when a semantic-annotation type
resolves to more than one body, rather than disambiguating. This item does not solve that
either: it matches a detection to the nearest existing piece of the same
`MontessoriShapeCategory`, greedily, one match per piece per tick. Adequate for the scenes
this plan measures (a handful of distinguishable pieces); recorded as a known simplification
rather than a general solution, consistent with how the codebase already treats the
ambiguous case elsewhere.

### The threshold, and what is deferred

`pose_change_threshold` is three standard deviations of position noise, measured by
repeating a look over one static simulated scene (reusing the `montessori_world`/
`camera_over_the_table` fixtures `test_montessori_simulated_camera.py` already uses) and
computing the sample standard deviation. The measured number is recorded in the test itself
once run.

**Deferred, not silently dropped:** the item's own notes ask for the threshold "measured in
simulation first and again on the robot, both numbers recorded." The robot half needs
physical robot access this session does not have. Recorded here as outstanding rather than
invented — whoever next has the robot records the second number against this same test's
simulation figure.

## 2026-09-09: `backends-declare-their-capabilities` kicked off, based on #265 rather than `tracy_icra`

Kicked off by `/plan-item-kickoff icra-mechanism backends-declare-their-capabilities`. #303.

### Base branch, same precedent as `snapshot-working-memory`

Checked directly rather than assumed: `git merge-base --is-ancestor
origin/claude/icra-experiments-simulation-pipeline-w4ep7n origin/tracy_icra` still answers no
(630 files / 86,630 insertions apart), so `tracy_icra` does not yet carry what this item needs —
`PerceptionDetector.capability`, `DetectorChoice`, `AttributeEqualityToLiteral.read_from` and
`QueryBackend` itself, all confirmed present on #265's tree. Same situation `snapshot-working-memory`
(#301) hit the same day, same answer: based on `claude/icra-experiments-simulation-pipeline-w4ep7n`
(#265), not `tracy_icra`. Will need restacking onto `tracy_icra` once
`tracy-demo-takes-the-integrated-branch` lands there.

### What already exists, checked against #265's tree before designing anything new

`krrood/src/krrood/entity_query_language/backends.py` already carries every piece the item's notes
point at: `AttributeEqualityToLiteral.read_from` reads an equality about the selected variable's own
attribute out of a condition; `QueryBackend` is the base class every backend already extends
(`SelectiveBackend`/`GenerativeBackend`, and concretely `EntityQueryLanguageBackend`,
`SQLAlchemyBackend`, `EntityQueryLanguageGenerativeBackend`, `ProbabilisticBackend`,
`PerceptionBackend`); and `PerceptionDetector.capability(look) -> ConditionType` /
`DetectorChoice` are the exact shape the item's notes say to raise from detectors to every backend.
None of `physics`, `motion-statechart` or `vision-language` backends exist yet — those are
`physics-verification-backend`, `control-constraints-and-degrees-of-freedom-queried` and
`perception-backends-are-interchangeable`, all of which depend on this item rather than the other
way round, so this item declares capability only for the backends already in the tree.

### Scope, as amended 2026-09-09 on #298's fourth round

Three parts, matching the amendment recorded in plan.yaml's notes:

1. `QueryBackend.capability()`, the same shape as `PerceptionDetector.capability(look)`: a method
   taking the thing being asked about and returning an EQL condition, rather than making
   `QueryBackend` generic over one bound type the way `PerceptionDetector[LookT]` is — a backend
   answers many different classes, not one `Look` subtype, so the generalization is in the method's
   signature (any `Selectable`), not in binding the class itself to a type parameter.
2. Field-level capability: a capability may name a specific field of a specific class as an EQL
   `Attribute`/`MappedVariable`, read back the way `AttributeEqualityToLiteral.read_from` already
   reads an attribute equality, rather than as a field-name string.
3. The underspecified-description helper: given a statement naming only a class (the developer's own
   example, `a(MontessoriBoard)`), add the features the twin already knows about that class to the
   description before a backend is chosen. Nothing does this today.

Tests pin one declaration per backend already in the tree against a statement it accepts and one it
refuses, following `detectors_that_state_what_they_answer.py`'s mimic-dataset pattern (a
`krrood`-only mimic in `test/krrood_test/dataset/`, per `AGENTS.md`'s self-containment rule for
`krrood`).

### Tooling bug found while recording this item, worked around rather than fixed here

`plan_item_bootstrap.py`'s `apply_item_fields` hardcodes `ITEM_FIELD_INDENT = "    "` (4 spaces)
and `ITEM_MARKER = "  - "` (2-space marker), matching `plans/README.md`'s schema example — but
every actual `plan.yaml` in this repo, this one included, uses 0-indent `- id:` markers with
2-space field indent instead. Patching or inserting a field through the script therefore
over-indents the written line, and where a folded (`>-`/`>`) field's body sits immediately above
the patched line, YAML reads the over-indented line as a continuation of that body rather than a
new key — reproduced here: patching `branch`/`pull_request_number`/`status` and inserting `session`
on this item corrupted the manifest (`while parsing a block mapping`, `expected <block end>`) every
time, confirmed by comparing byte-identical inputs across three runs. Worked around by hand-patching
the four fields at the file's actual 2-space indent and pushing directly, per `plans/README.md`'s
"Editing an existing plan" section, rather than through `open`/`record`. Not fixed here — it is
shared session tooling on `main`, unrelated to this item's own subject, and worth a
`plan-tracking-skills` item of its own; every other in-flight kickoff that needs `apply_item_fields`
to patch or insert a field is exposed to the same corruption until it is.

### `snapshot-working-memory` built, #301: the measured threshold turned out to be a numerical floor, not a perceptual one

Implemented `SnapshotWorkingMemory` per the plan above. One finding worth recording because
it changes what "the threshold is measured in simulation first" actually produces: repeating a
look at an *unchanging* simulated scene reproduces the same detected position to within
floating-point noise (~1e-15 m) — MuJoCo's render is close enough to bit-for-bit deterministic
that three standard deviations of it is a number too small to guard against anything but the
computation's own numerical floor, not real perceptual noise.

So `POSE_CHANGE_THRESHOLD_METERS` (`1e-6` m) is documented as a numerical safety margin above
that measured floor, not a literal three-sigma figure — large enough that no repeated look ever
crosses it on its own, and still many orders of magnitude below any real piece movement. The
real, meaningful three-sigma figure the item's notes ask for is expected from the real robot,
where sensor noise is not zero; that measurement still needs the robot and is not taken here.
Recorded so a later session does not read the simulated number as if it settled the real one.

Also: the matching strategy (nearest existing piece of the same `MontessoriShapeCategory`,
greedy, one match per piece per tick) does not solve general multi-instance disambiguation —
consistent with `coraplex.perception.Detection.apply_to`, which raises (`AmbiguousDetection`)
rather than disambiguating a type that resolves to more than one body. Adequate for this plan's
scenes; flagged rather than silently assumed general.

Tests run against the real MuJoCo pipeline in a from-scratch Python 3.12 venv this session built
(the container ships neither ROS nor 3.12 by default, and `random_events_lib`'s native
extension had to be compiled locally for 3.12). All 8 new tests and the 15 in
`test_montessori_simulated_camera.py` (checked for regressions from a shared relative import)
pass.

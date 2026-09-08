# icra-evidence: roadmap

One of three successors of `icra-experiments`, split 2026-09-05 for the plan
size budget (`plan-size-limits`, tracking issue #200) — the item limit alone
(33 > 15), not the line budget. The split is by wave, the plan's own
existing organizational seam: `icra-foundation` is the `foundation` wave,
`icra-mechanism` is `mechanism`, `icra-evidence` (this plan) is `evidence`.
All three keep `tracking_issue: 252`, the original mailbox. Full split
rationale and what it cost lives in `plan-size-limits/roadmap.md`'s "Done
2026-09-05: `split-icra-experiments`" section; the predecessor's full
roadmap is reachable in the personal-notes branch's history immediately
before the split commit.

**Every item in this plan except `benchmark-artifact` and
`resource-cost-measured-per-system` depends on at least one item in
`icra-foundation` or `icra-mechanism`** (eleven of this plan's thirteen items
carry a cross-plan `blockers` entry instead of a `depends_on` edge, since
`depends_on` cannot cross a plan boundary — see plan.yaml). Read
`icra-foundation`'s roadmap first for the programme's overall "why"; this
file states only what is specific to this wave.

## Why this wave exists

The memo's evidence is experiments on the UR10, each run end to end in
simulation first: **A**, question answering against a VLM with and without
verbalised working memory; **B**, per-predicate backend decomposition of a
mixed query plus a perceive-commit-verify loop under injected errors; **C**,
insertion under knowledge ablations and perturbations, every failure typed
and predicted; and **D** (added 2026-09-04, see below), the same questions
asked of the recorded episode history rather than the current scene. The
`efficiency` track (added 2026-09-08) measures what every answer costs on
every system, and the `release` track packages what they all produced.

Since 2026-09-08 the experiments are organised by the level of Bloom's
taxonomy each exercises — **D** is Remembering, **A** is Understanding, **C**
is Applying, and **B** is the demonstration that all three run on one
representation. Bloom is the evaluation frame and the way the queries are
taxonomized; it is not a claim about the architecture. See "2026-09-08"
below for the frame, the six question buckets, and the levels the paper
declares out of scope.

## The budget: 2026-09-15

Twelve days from 2026-09-03. The memo's own timeline is kept where it holds
and moved where the plans showed it could not.

| when | lane 1 | lane 2 | lane 3 | state reached |
|---|---|---|---|---|
| Thu 3, Fri 4 | integrated pipeline; simulated camera | domain model; episodes recorded | question set frozen; memory verbalised | the simulated demo runs the whole pipeline and records episodes |
| Sat 5, Sun 6 | capabilities; routing | scenarios; taxonomy; ablations; perturbations | VLM harness; figures script | go/no-go Sunday evening: routing and physics verification answer a mixed query in simulation |
| Mon 7, Tue 8 | physics verification; snapshot memory; tracy takes the branch (robot Tue) | episodes queried; prediction; Experiment C in simulation | Experiment A in simulation | **every experiment has run once in simulation** |
| Wed 9, Thu 10 | Experiment B in simulation, then robot A | robot C | robot A ground truth, tables | robot numbers for A and C |
| Fri 11 | robot B | reruns | experiments section | full first draft |
| Sat 12, Sun 13 | video | reruns | artifact; internal review | reviewed draft, artifact |
| Mon 14, Tue 15 | | | tighten, limitations, submit | submitted |

Lanes 1/2/3 span all three successor plans (see `icra-foundation`'s and
`icra-mechanism`'s roadmaps for their own lane assignments); this wave's own
lane order: **lane 1** ends in `experiment-b-in-simulation` then the three
robot runs; **lane 2** carries `experiment-c-in-simulation`, then
(2026-09-04 addition) `episode-artifacts-recorded` (in `icra-foundation`) →
`cross-episode-question-set-and-ground-truth` → `experiment-d-in-simulation`;
**lane 3** is `question-set-and-ground-truth` → (`icra-mechanism`'s
`working-memory-verbalised`/`vlm-baseline-harness`) → `paper-figures-from-episodes`
→ `experiment-a-in-simulation` → `benchmark-artifact`, writing the paper's
sections 1–4 in the gaps and the experiments section from the generated
tables.

If the go/no-go fails, the memo's fallback holds: submit with A and C and
drop B's injection half, keeping the decomposition numbers from #238.

**Cut order**, unchanged from the memo: lighting → the optional
no-narrowing ablation → a second setup → fewer random scenes → B's injection
half. **Never cut:** the temporal scenarios, the perturbation conditions,
the hybrid VLM baseline, the failure-prediction metric, the determinism
runs.

## Cross-plan prerequisites relevant to this wave

- **knowledge-directed-perception**'s `expectations-from-events` (not
  started there) is the failure-detection story: without it,
  `experiment-c-in-simulation` reports typed failures but not detected ones
  (blocker already on that item, unchanged by this split).
- **montessori-eql-stack**'s console stack above #169 is not needed for any
  number in the paper; #168's presets are reused by
  `question-set-and-ground-truth` as EQL text only. The video for `release`
  may want the console — a 2026-09-12/13 decision.

## 2026-09-04: Experiment D, because long-term memory was built but never scored

The developer noticed the plan tracked no long-term-memory *experiment* —
`icra-foundation`'s `episodes-recorded-through-ormatic`/`episodes-queried-by-eql`
build the machinery, but Experiments A–C all ask about the current scene, so
the long-term-memory spelling of the temporal bucket that
`question-set-and-ground-truth` explicitly names had no consumer, even
though the plan's own description calls long-term memory a deliverable.

**Three decisions, and why:**

- **Its own experiment, not a fourth bucket of A.** A and D put different
  systems under test — one VLM looking at the current scene's image, one VLM
  reading a corpus of past episodes — with different ground truth and a
  different fairness argument. Folding them would mix two incomparable
  systems into A's per-bucket accuracy table.
- **Simulation only**, decided 2026-09-04: the questions are about recorded
  episodes, so they do not care whether an episode came from the robot or
  the simulator — the robot episodes A and C record join the same corpus for
  free. The condition is that simulated episodes must record video and
  simulation data, which is `icra-foundation`'s `episode-artifacts-recorded`.
- **The VLM gets the whole corpus, capped so it fits — not a retrieval
  step.** Retrieval was considered and rejected: it scales to any corpus,
  but a wrong answer is then ambiguous between "retrieval never surfaced the
  episode" and "the model had it and reasoned wrong", exactly the
  distinction the experiment exists to make. Capping the episode count,
  derived from what the model's context holds once video frames are
  sampled, means the model is provably given everything the SQL backend can
  see over the same episodes, so a loss reads as a reasoning failure. The
  cap becomes the baseline's stated limitation in the paper, and it also
  simplifies the availability metric: with one shared corpus, whether the
  needed information is present at all is a property of the corpus measured
  once, not a per-system score.

`cross-episode-question-set-and-ground-truth` spells the four kinds of
question (has this happened before and in which episode; what the goal and
conditions were then; what differed between episodes that bears on the
question; how a failure was resolved last time), the last of which is why
`icra-foundation`'s episode model grew `FailureResolution`. Ground truth is
read from the recorded trial log directly, never through the query under
test.

**Left to the developer:** re-budgeting the eleven-day deadline for a fourth
experiment. One suggestion, not decided here: if time runs short, cut D's
VLM arm first and keep the EQL-over-SQL numbers, which need no external
model or credentials — the same shape the memo's own cut order already
takes with B's injection half.

## 2026-09-08: Bloom as the evaluation frame, six buckets, and cost beside correctness

Refocus pass across all three ICRA plans; the developer's direction is quoted
in `icra-foundation`'s roadmap, and the structural changes to the other two
waves are in their own roadmaps. What changed here is what the paper measures
and in what order.

### The frame

Three levels, each with an experiment already built for it:

- **Remembering** — the store is queried and the facts come back. Measured
  over long-term memory and against a vision-language model given the same
  episodes, with the resources each needed. Experiment D.
- **Understanding** — the developer's own definition, recorded here because
  the paper states it: *the ability to interpret information presented to you
  in at least one of several forms (verbally, symbolically, graphically) well
  enough to answer direct questions about it in your own language* — which
  here is the programming language, the domain model and the query language.
  Understanding can be spatial, temporal or logic-based. Measured by
  correctly answering the question set. Experiment A.
- **Applying** — the demo runs on the whole representation, then with parts
  of it removed, and the difference is the measurement. Experiment C.

**Explicitly out of scope**, stated in the paper rather than left for a
reviewer to raise: inferring new knowledge, or any question needing several
facts combined to reach a conclusion that is not already represented. *"What
objects can you pick up, and why or why not"* is the named example. It is
above Understanding, and claiming it would be claiming something the
evaluation does not measure.

**Working memory has no level in the taxonomy, and that is a finding rather
than a gap.** Several of the questions the paper cares most about — did
anything recently move, which, *did you move it* — cannot be answered from a
single observation at all, only from a store that persisted across time and
that distinguishes what the robot did from what happened to it. The taxonomy
does not name that capacity; the paper argues it is nonetheless required, and
`icra-mechanism`'s `snapshot-working-memory` is the mechanism that supplies
it.

### The question set, widened from four buckets to six

`question-set-and-ground-truth` was "the twelve questions in four buckets".
It is now six, because the control program and the robot's own body have to
be questioned in the same language as the scene or the integrative claim is
only about perception and memory:

| bucket | the questions |
|---|---|
| scene | What objects do you see now? What colours are they? Where are they? |
| support and spatial relations | What surfaces are they standing on? Is the cube left or right of the cylinder? |
| temporal and agency | Did any object recently move? Which? Did *you* move them? Was the cube recently picked up? |
| embodiment | Is it currently in your hand? |
| self-model | Where is your gripper left finger located? How many links do you have? How many joints do you have? |
| control | What are you constrained by right now? Which task is active? Why did the motion stop? |

The self-model bucket is answered from structure the twin already holds —
bodies, connections, degrees of freedom and their limits — which is the point:
the same representation the controller optimizes over is the one that answers
how many joints the robot has. The control bucket needs
`icra-mechanism`'s `control-reads-the-twin-as-constraints` to publish the
active tasks and constraints back into the twin.

**Every bucket now has two spellings**, over working memory and over
long-term memory, where before only the temporal bucket did. That is what
makes Understanding and Remembering separately measurable on the same
questions.

### `question-set-answered-from-memory`, new and moved to the front

The plan had no item where the questions were simply *answered by our own
system and scored* — the first item that asked them was
`experiment-a-in-simulation`, which asks them of EQL and two VLM systems at
once and therefore waits on the VLM harness, the verbalised memory and a
provider decision that is still open. The developer asked to *"prioritize
answering the questions in the long term memory system and in the working
memory as fast as possible and as parallel as possible"*, and this is that
item: all six buckets, both spellings, scored against ground truth, no
external model anywhere in it.

It splits cleanly in two, which is what makes it parallel: the working-memory
half runs against a live simulated scene, the long-term-memory half against
the recorded corpus, and neither waits for the other. With
`episode-artifacts-recorded`'s dependency on the perception lane removed (see
`icra-foundation`'s roadmap), the long-term-memory half is a lane one person
can carry from the episode model to a scored table without touching lane 1.

It is also the fallback: if the baseline arms are cut for time, the accuracy,
latency and footprint tables still exist, because they never needed the
baselines.

### `resource-cost-measured-per-system`, new track `efficiency`

The comparison against vision-language models is a cost comparison, so the
cost is measured rather than asserted. Per question and per system:
wall-clock latency, processor time, peak resident memory, and the size of
what had to be held — the database on disk and in memory for the query
backends, the parameters and the tokens sent and received for the
vision-language arms, with the monetary and energy figures those imply and
the assumption behind each stated. Reported per bucket and per Bloom level
rather than as one aggregate, because recall from a database against recall
from a sampled video corpus is a different comparison from answering a
spatial relation about the scene in front of the robot.

Its own track because it instruments every experiment rather than being one.
Every number comes from episode rows the runner already writes, so the
figures script regenerates the table rather than anyone transcribing it.

### What this costs, given the budget

The budget table above still says **2026-09-15**, and this refocus lands on
2026-09-08 — one week, not twelve days. Nothing in the table was rewritten
here, because re-budgeting is the developer's and the memo's timeline is his
record. What the refocus does say about the order, and what the items now
carry:

- The three things to hold are `question-set-and-ground-truth`,
  `question-set-answered-from-memory` and
  `icra-foundation`'s `episode-corpus-generated-at-scale`. They are the
  Remembering and Understanding results, they need no external provider, and
  they now run in parallel across two people from the day the question set is
  frozen.
- `control-reads-the-twin-as-constraints` is the one new mechanism item on the
  critical path, because without it the control bucket has no answers and
  Experiment C's degree-of-freedom ablation stays a code branch.
- `physics-verification-backend` moved off the critical path and is cut
  first, ahead of the memo's existing cut order (lighting → the optional
  no-narrowing ablation → a second setup → fewer random scenes → B's
  injection half). `perception-backends-are-interchangeable` is next after
  it — it is the sharpest demonstration of the claim, but the claim survives
  its loss where the memory results do not.
- **Never cut**, revised: the temporal and agency questions, the perturbation
  conditions, the failure-prediction metric, the determinism runs, and — added
  here — the resource-cost table, which is what the vision-language
  comparison is for. The hybrid VLM baseline stays on the never-cut list from
  the memo, but it is no longer what establishes the paper's own numbers.

### Left to the developer

- The budget table has not been re-cut for the week that remains, or for the
  two new critical-path items. That is the one thing this refocus did not do.
- Which vision-language model and provider the harness calls is still open
  (`icra-mechanism`'s roadmap carries it), and it now blocks less than it
  did: nothing in `question-set-answered-from-memory` needs an answer to it.

### `question-set-and-ground-truth` (#295), as planned 2026-09-08

Lane 3's foot item, and the first item of this plan to open a branch.

**Cut off #278 (`episodes-queried-by-eql`), not off `main` and not off #271.**
A question's long-term-memory spelling is an EQL query answered from the
recorded episodes, and `LongTermMemory.answer(query)` is exactly that seam —
one `FromDataAccessObjectState` per answer, a session opened from the
database object it was given. Asking over a bare `Session` here would have
been a second copy of that conversion path in a second package. #278 is open
and not a draft, so it counts as ready to build on, the same reading #278 and
#294 were themselves cut under; and it carries #271, #262 and #261, so both
of this item's recorded cross-plan blockers are satisfied through it.

**One `Question` class, generic over what it is asked of and what it
answers.** The item asks for a dataclass carrying its EQL, its English, its
answer type, its Bloom level and the inputs it structurally requires, and
that is what it is — no second class for a question that has no spelling
yet. `Question[SourceType, AnswerType]` inherits `SubClassSafeGeneric`, so
`answer_type` and `source_type` are read back off the binding rather than
kept as fields that can disagree with it. `english`, `bucket` and
`required_facts` are fields; `query(source)` is the EQL, `ask(source)`
evaluates it, and `ground_truth(source)` reads the same answer off the twin
directly, never through the query under test.

**The Bloom level comes from the memory, not from a field.** Two abstract
bases bind the source: `WorkingMemoryQuestion` over a live twin and its
segmind event log (Understanding), `LongTermMemoryQuestion` over the
recorded episodes (Remembering). The roadmap's own definitions make the
level a property of which memory answers, so a per-question field could only
ever disagree with the one thing that decides it. This is also what makes
Understanding and Remembering separately measurable on the same English
question, which is what the two spellings are for.

**`WorkingMemory` names what a live question is asked of** — the world, the
robot in it and the events segmind has seen — rather than passing three
arguments to every question. It is what working memory *is*;
`icra-mechanism`'s `snapshot-working-memory` is how it is kept current, and
that item is untouched here.

Six buckets as `Bucket`, three levels as `BloomLevel`, the two spellings as
`Memory`, the structural requirements as `RequiredFact`, and where a true
answer comes from as `GroundTruthSource` (the twin in simulation, exact; the
calibrated twin plus a human check on the robot). `QuestionSet` holds the
frozen set and answers `for_bucket`/`for_memory`/`for_bloom_level`; the set
is built by a classmethod rather than a module-level constant.

#### What is spelled here, and what waits — the honest half of the freeze

The item's contract is six buckets in two spellings. Not all twelve can be
written today, and the gaps are recorded here rather than stubbed in code:

| bucket | over working memory | over long-term memory |
|---|---|---|
| scene | spelled | spelled |
| support and spatial relations | spelled | waits |
| temporal and agency | spelled | spelled |
| embodiment | spelled | spelled |
| self-model | spelled | waits |
| control | waits | waits |

- **control, both spellings** — already recorded on the item's own blocker:
  nothing names a task's constraints or the degrees of freedom it used until
  `icra-mechanism`'s `control-constraints-and-degrees-of-freedom-queried`,
  so there is no EQL to freeze, in either memory.
- **self-model over long-term memory** — the item's blocker says this waits
  on #271, "which is where the episode gains a reference to the world it ran
  in and the motion statechart it ran". Checked against #271 as it stands:
  `Episode` carries the scenario name, execution type, condition and
  perturbation names, an identifier and a timestamp, and `RecordedTrial`
  carries outcome, duration, ticks, queries and insertion attempts —
  neither references a world or a statechart. The fold recorded in
  `icra-foundation`'s roadmap on 2026-09-08 has not been implemented on that
  branch yet, so the blocker still holds exactly as written. The
  working-memory spelling needs none of it and is written here.
- **support and spatial relations over long-term memory** — not previously
  written down, and it is the one gap this plan did not already record.
  `LeftOf`/`RightOf`/`SupportedBy` are geometric predicates evaluated over a
  world; answering them from the SQL backend is a routed predicate, which is
  `icra-mechanism`'s `query-routed-per-predicate`. The support half is
  partly recoverable from recorded `SupportEvent`s, and is spelled that way
  where the event log carries it; the view-dependent relations are not.

#### The hazard this item was warned about, and is the first to meet

`icra-foundation`'s roadmap records, on #278: *"The to-many collections an
episode holds — ticks, queries, insertion attempts — are reached through
association tables, and no test in this repository proves EQL translates a
join across one; nothing here depends on that, and finding out belongs to
whichever item first needs it."*

This item is that item. Every long-term-memory spelling of the scene,
temporal-and-agency and embodiment buckets reaches `RecordedTrial.ticks` and
then `Tick.events`, which is two to-many hops. The spellings are written the
natural way and the tests assert the answers against ground truth read off
the recorded objects directly, so **CI is what answers the question** — the
workspace cannot be installed in a session container (`random_events`,
`antlr4-python3-runtime`, `arff` and `dnutils` all fail to build there), the
same standing limitation every item of this track has recorded. If the
translation does not hold, the finding belongs on this branch and the
spellings change shape in one place: `LongTermMemoryQuestion.query`.

#### Testing

`test/experiments_test/test_questions.py`, in two halves. The working-memory
half builds a small world of two shapes on a surface, with a robot holding
one of them, and asks every working-memory question of it, asserting each
answer equals the ground truth read off the twin. The long-term-memory half
records an episode through #271's own recorder into a SQLite file — the
shape `test_long_term_memory.py` already uses — and asks every long-term
question of it. Both halves also assert the frozen set itself: that every
bucket is represented, that a question's Bloom level follows its memory, and
that `required_facts` names what the question actually reads.

CI-only, per the standing ROS/`random_events` limitation.

### `question-set-and-ground-truth` (#295), as built 2026-09-08

What changed against the plan above, and what was found while building it.

**The container limitation this track has recorded throughout is out of date.**
Every item of the `long-term-memory` track says the workspace cannot be
installed in a session container because `random_events` needs a native library
whose PyPI build fails. It installs fine. The three packages that actually
failed -- `arff`, `dnutils` and `antlr4-python3-runtime` -- fail against the
Debian-patched `setuptools` a system Python carries, and build without
complaint in a fresh virtual environment; `giskardpy_bullet_bindings` is on
PyPI too. What genuinely still needs CI is *ORM generation*, because giskardpy's
`DebugExpressionPublisher` imports a real `rclpy`.

So the split is not "session versus CI" but "does this touch the generated
interface". The working-memory half touches none of it and was run here against
a real twin -- 20 tests, every question asked of a built scene and checked
against ground truth. The long-term half is CI-only, as before.

**The developer chose to write the long-term half rather than split it out**,
and to fix #271 in the same pass. Both were put to him because they change what
the item delivers: the long-term spellings could not be run here at all, and
#271 is another plan's branch.

#### #271 grew the two references its own fold had promised

`icra-foundation`'s roadmap recorded on 2026-09-08 that
`self-model-and-control-state-recorded` folded into
`episodes-recorded-through-ormatic` because "that is a field or two, not an
item". The fold was recorded but never made: `Episode` named the scenario, the
conditions and an identifier, `RecordedTrial` named the outcome, the ticks, the
queries and the attempts, and neither named the world the run happened in or the
motion the trial ran. `a96531635` on that branch adds `Episode.world` and
`RecordedTrial.motion_statechart`, both optional, with three round-trip tests,
and its description and a comment record why. Whether a corpus keeps a world per
episode or shares one is still the developer's open call -- the field allows
both.

#### What the six buckets actually got

| bucket | over working memory | over long-term memory |
|---|---|---|
| scene | three questions | one question |
| support and spatial relations | two questions | waits |
| temporal and agency | four questions | four questions |
| embodiment | one question | waits |
| self-model | three questions | one question |
| control | waits | waits |

Three gaps, and each is now a specific statement rather than a guess:

- **control, both spellings** -- unchanged from the item's own blocker: nothing
  names a task's constraints or the degrees of freedom it used until
  `icra-mechanism`'s `control-constraints-and-degrees-of-freedom-queried`.
  `RecordedTrial.motion_statechart` is now recorded, so that item has something
  to be written against, but naming the constraints is still its work.
- **support and spatial relations over long-term memory** -- the spatial
  relations are geometric predicates evaluated over a world. Answering them from
  rows is a routed predicate, which is `icra-mechanism`'s
  `query-routed-per-predicate`. Not previously recorded anywhere; it is the one
  gap this plan had not anticipated.
- **embodiment over long-term memory** -- reduces to the pick-up record, which
  the temporal bucket already asks, unless an episode also records *which links
  were the robot's*. Recording the world does not answer that: an object the
  robot picks up hangs off one of its links without becoming one, and nothing in
  a recorded world tells the two apart. Whoever needs it decides whether an
  episode should record the robot's own links as well as its world.

#### Design calls taken while building

- **The Bloom level comes from the memory, not from a per-question field.** The
  roadmap's own definitions make the level a property of which store answers, so
  a field could only disagree with the one thing that decides it. It is also
  what makes understanding and remembering separately measurable on the same
  English question.
- **`WorkingMemory.own_bodies` is given rather than derived.** The first attempt
  read the robot's links off the kinematic branch under its root and was wrong
  the moment anything was grasped: a held object is in that branch, so it counted
  as a link and the objects list lost it. Which links the robot is made of is
  knowledge working memory holds, not something the twin still says afterwards.
- **"Is it in your hand?" is answered from the attachment, not from
  `bodies_in_gripper`.** `icra-foundation`'s roadmap names `bodies_in_gripper` as
  how the twin answers gripper contents, and it does -- geometrically, by casting
  rays between the fingers. Working memory is what the robot *believes* it is
  holding, which is what a grasp writes into the twin and a release takes out.
  Different questions; this bucket asks the second.
- **"How many joints do you have?" counts degrees of freedom**, not connections:
  a fixed connection joins two links without being a joint anything can move.
- **"Is the cube left or right of the cylinder?" is frozen as the two questions
  it decomposes into**, one per side, each a single query answering a judgement.
  The alternative -- one question answering which relation holds -- needs either a
  Python branch over two queries or an aggregate the query language does not
  translate here.
- **`is_on_side_of` is ours.** The twin's `LeftOf`/`RightOf` relate `Point3`s and
  are plain `Symbol` dataclasses, which the query language rejects as a
  condition (`LiteralConditionError`). One `symbolic_function` adapting them to
  the two bodies a question is about is what lets the bucket be asked in the
  query language at all; `Side` carries which relation it means, so left and
  right are spelled once.
- **The self-model spelling over long-term memory selects rather than counts.**
  `LongTermMemory.answer` converts every row it gets back into a domain object,
  so an aggregate has no way through it. The live spelling uses `count`; the
  recorded one selects the degrees of freedom and takes how many came back. If
  the counting matters at corpus scale, a counting method on `LongTermMemory` is
  that item's work.

#### The hazard, still open

`icra-foundation`'s note on #278 -- that nothing proves the query language
translates a join across the association table an episode's to-many collections
are reached through, and that finding out belongs to whoever needs it first --
is still the largest risk on this branch. Every long-term question crosses one,
most of them twice (`RecordedTrial.ticks`, then `Tick.events`).
`test_long_term_questions.py` is what answers it, and CI is where it runs. If it
does not translate, the shape changes in one place -- each question's `query` --
and the finding belongs on this branch.

### `paper-figures-from-episodes` (#297), as planned 2026-09-08

Lane 3's writing item, and the second item of this plan to open a branch.

**Cut off #278 (`episodes-queried-by-eql`), not off `main` and not off #295.**
The item's one recorded blocker is #278, and `LongTermMemory.answer(query)` is
the seam every table here reads through: a figure is an EQL query over the
recorded episodes plus an aggregation of the domain objects it answers with.
#278 is open and not a draft, so it counts as ready to build on, the same
reading #295 was cut under, and it carries #271 (the episode model), #262 (the
database) and #261 (the scenario model).

Not #295, even though the two are lane 3 neighbours and #295 is the nearer
sibling: it is still a draft, so it is not ready by the plan's own rule, and
the tables it would unlock — accuracy per bucket, per Bloom level — need
*recorded answers* to those questions, which is
`question-set-answered-from-memory`'s work and has not run. Waiting on it would
buy nothing. The item's recorded blocker also said `episodes-queried-by-eql`
was `not_started`, which it has not been since #278 opened; the blocker is
cleared here rather than carried stale.

**What an episode currently records is what bounds the script.** The item's
contract is "every table and figure in the paper", and the honest reading of
that on 2026-09-08 is every table the recorded model can already produce. An
`Episode` carries its scenario, execution type, conditions and perturbations; a
`RecordedTrial` its outcome, duration, ticks, queries and insertion attempts; an
`InsertionAttempt` its predicted and observed failure and how it was resolved; a
`RecordedQuery` its text, answer, latency and the backend each predicate was
routed to. Six tables follow from that, and each is one the paper prints:

| figure | what it reports | whose experiment |
|---|---|---|
| trial outcome by condition | success rate per ablation condition, with its interval | C |
| failure type by condition | observed failure types counted per condition | C |
| failure prediction | precision and recall of predicted against observed failure | C |
| query latency by backend | how many predicates each backend answered, and how long | B |
| query determinism | how often a repeated question came back with the same answer | A, D |
| trial outcome by execution type | simulation against the robot | A, C |

Three of these are on the roadmap's own never-cut list (the failure-prediction
metric, the determinism runs, the perturbation conditions' outcomes).

**What is not here, and which item owns it.** Accuracy per bucket and per Bloom
level waits on `question-set-answered-from-memory`, which is what first records
a question's answer as an episode row. The resource-cost table waits on
`resource-cost-measured-per-system`, which is what adds processor time, peak
resident memory and corpus size to a recorded query — `RecordedQuery` carries
latency alone today. Neither is stubbed here: the figure each needs is a
`PaperFigure` subclass, and adding one is the work of the item that adds the
column it reads.

The stacked failure-type bars the plan names are drawn from the failure-type
table rather than rendered here. `TypstRenderer` renders tables, and giving it a
bar chart is a rendering change with no episode data behind it.

#### Design

- **A figure is a class, and the set of them is built by a classmethod**, the
  shape `QuestionSet` already takes on #295. `PaperFigure` carries the name it is
  written under and its caption, and answers `rows(trials)`; `FigureSet` holds
  every figure the paper prints and writes them all.
- **Read with EQL, aggregate in Python.** The figures select whole
  `RecordedTrial` objects and traverse their collections, rather than asking the
  query language to join across the association tables those collections are
  reached through — the hazard `icra-foundation` recorded on #278 and #295 was
  the first to meet. `report_on` already traverses `trials[0].episode` the same
  way. If #295's CI run shows the join translates, nothing here has to change to
  benefit; the reverse is not true.
- **Every rate carries its interval.** `ConfidenceInterval.for_mean` and
  `MeanAndStandardDeviation` already exist and are what the item's "confidence
  intervals on every rate" asks for; a rate is the mean of a per-trial
  indicator, so the same summary serves both.
- **A figure's file name is an enum member, not a string.** `FigureName`'s
  members are the file stems the script writes, so the paper and the script name
  the same figure once.
- **The script writes the JSON manifest beside every table.**
  `ExperimentsTable.write_manifest` already exists for exactly that, and it is
  what makes a number in the paper traceable to the rows it came from.

#### Testing

`test/experiments_test/test_paper_figures.py` builds recorded trials in memory
and asserts each figure's rows against values read off those trials — no
database, so it runs anywhere the workspace imports.
`test_paper_figures_from_the_database.py` records the same corpus through the
recorder a run uses and asserts the figures regenerated through `LongTermMemory`
equal the ones computed in memory, which is what "regenerated from the episode
database" actually claims. That half is CI-only: it needs the generated ORM
interface, and generating it needs ROS.

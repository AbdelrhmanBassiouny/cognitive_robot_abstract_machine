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

### `paper-figures-from-episodes` (#297), as built 2026-09-08

What changed against the plan above, and what was found while building it.

**The six tables the plan named are the six that were built**, in
`experiments/src/experiments/paper/`: trial outcome per ablation and per
execution type, the failure types each ablation produced, the precision and
recall of failure prediction, what each backend answered and how long those
queries took, and whether a repeated question came back with the same answer.
`LongTermMemory` gained `recall_every_trial`, the one question the script asks
it — a table reports the whole corpus, and `recall_trials` only reaches one
episode's.

**Two things the plan did not anticipate, both about where these tests can
run.**

- `test/experiments_test/conftest.py` regenerates the ORM interfaces for
  *every* test in that package, and that generation still fails in a session
  container on giskardpy's `DebugExpressionPublisher`, exactly as #295
  recorded. So the in-memory half is CI-only in-tree even though it needs no
  generated interface of its own. It was verified here by running a copy of it
  outside that package — 23 tests, every row checked against the value the
  corpus determines, all passing.
- #295's correction ("the split is not session versus CI but does this touch
  the generated interface") is very slightly too narrow.
  `experiments.episodes.episode` reaches ROS at import time through
  `segmind.datastructures.events`, which imports `geometry_msgs`, and that is
  not on PyPI. So anything touching the episode model needs ROS message
  packages present, generated interface or not.

#### Design calls taken while building

- **Read with EQL, aggregate in Python.** Each figure selects whole
  `RecordedTrial` objects and walks their collections rather than asking the
  query language to join across the association tables those collections are
  reached through — the hazard `icra-foundation` recorded on #278, which #295
  is the first to meet. `report_on` already traverses `trials[0].episode` the
  same way. It also means this branch benefits if #295's CI run shows the join
  translates, and is unaffected if it does not.
- **A rate is the average of a per-trial indicator.** One `MeasuredQuantity`
  therefore serves a success rate, a failure share, a precision and a latency
  alike, and every number in the paper carries its interval without a second
  summarizing path existing.
- **A quantity measured over nothing is left out rather than reported as
  zero.** Precision over no prediction, or a failure share over no attempt, is
  undefined; a zero there reads as a system that never foresaw anything.
- **A question asked once is not reported as deterministic.** One asking always
  agrees with itself, so including it would fill the determinism table with
  rows of ones on the one subject it exists to measure.
- **The success rate is measured with `GoalReached`**, the metric a run's own
  report already uses, so a table regenerated from the database says what the
  run said rather than something computed a second way.
- **Every table sorts its own rows**, each by what actually orders that table:
  the unablated run first (which is what `RunConditions`'s ordering is for),
  backends and questions alphabetically, precision before recall. The database
  returns trials in no particular order, and a regenerated paper table must not
  reshuffle between runs.
- **The stacked failure-type bars are drawn from the failure-type table rather
  than rendered here.** `TypstRenderer` renders tables; a bar chart is a
  rendering change with no episode data behind it, and it would be the only
  part of this item not regenerated from the database.

#### What waits, and on which item

- **Accuracy per bucket and per Bloom level** — `question-set-answered-from-memory`
  is what first records a question's answer as an episode row. Nothing here
  reads a bucket or a level because no row carries one yet.
- **The resource cost table** — `resource-cost-measured-per-system` is what adds
  processor time, peak resident memory and corpus size to a recorded query;
  `RecordedQuery` carries latency alone.

Neither is stubbed. The figure each needs is one `PaperFigure` subclass, so
adding it belongs to the item that adds the column it reads.

#### A bug in the plan tooling, found while bootstrapping this item

`plan_item_bootstrap.py`'s `open` and `record` write an item's fields at the
wrong indentation when that item's `title` is a folded block scalar (`>-`):
`branch`, `pull_request_number`, `status` and `session` land indented under the
title's continuation line, and `save-plan.sh` then rejects the manifest as
invalid YAML. Every item in this plan has such a title, so both operations fail
for all of them. This item's manifest entry and this roadmap section were
written by hand instead. Reported to the developer; not fixed here, since it is
tooling on `main` and unrelated to this branch.

### `question-set-and-ground-truth` (#295), reviewed 2026-09-08

Eight review threads, and the substance of them was one objection: the questions
were handed what they should have asked for. What came back from acting on it,
and the two defects the round measured.

#### Nothing is handed to a question

`WorkingMemory` held the world, the robot's links, the point of view and the
event log, and every query took a domain computed from one of them. All of it
was unnecessary, and the reviewer named the reason: the symbol graph already
tracks it. Measured before changing anything --

```
Body is Symbol            : True
DegreeOfFreedom is Symbol : True
DetectionEvent is Symbol  : False     <- the one thing missing
variable(Body) no domain  : ['cube', 'ball']    <- resolves from the graph
```

-- so `DetectionEvent` now inherits `Symbol` and an event joins working memory
by being made. Every variable is domainless and what a question is about is a
condition on it. What is left of the source is the robot, which is whose memory
it is and where its own links and its hand are read from, so
`WorkingMemoryQuestion` is `Question[AbstractRobot, AnswerType]`.

The graph holds instances **weakly**: it tracks what is alive rather than
keeping it alive, so an event nothing holds is one the robot no longer
remembers. Defensible as a definition of working memory, and worth knowing
before anyone relies on it -- a test has to hold its own events.

`QuestionSet` is now read off the question subclasses rather than from a list,
with each question carrying an `asked_of(things)` classmethod saying how a scene
fills it in. Order is written order, which is bucket order because each module
is laid out bucket by bucket.

#### `exists` is wrong here, and worse than the plan predicted

`eql-existential-semantics` records that `exists` drops matching rows. Over the
agency question's shape it does something else: three objects, the robot picked
up and moved two, the third only moved --

```
exists-based answer : ['cube', 'ball', 'untouched']
join-based answer   : ['cube', 'ball']
```

It returns *every* object that moved. The original test passed only because its
scene had exactly one motion event, which is the same accident that roadmap says
every existing `exists` test in the repository relies on. Nothing in that plan is
implemented, so there was no fix to merge; both spellings use the plain join and
`exists` is gone from this branch.

#### The association-table hazard, answered in two halves

`icra-foundation`'s note on #278 -- that nothing proves the query language
translates a join across the association table a to-many collection is reached
through, and that finding out belongs to whoever needs it first -- is answered,
and the answer is in two halves. Both were reproduced in krrood's own test
dataset, so the finding is recorded where the defect is rather than where it was
noticed.

- **Selecting a collection returned the association rows, not the members.**
  Fixed: `_apply_relationship_join` now follows an association object through to
  its target. `test_selecting_a_collection_yields_its_members` covers it.
- **Membership as a condition still does not join.** Each variable translates to
  its unaliased data access object, so an owner and a member whose classes share
  a mapped base cannot be told apart in the ON clause. Left as a strict xfail,
  `test_membership_in_a_collection_joins_the_members`. The fix is per-variable
  aliasing in the translator, which is EQL work rather than this item's, and it
  is what the long-term half now waits on.

So the long-term spellings are frozen in the shape they will be asked in, with
their answering tests expected to fail. **This item's long-term half produces no
accuracy table until that lands**, which is a harder statement than the previous
"thinner than the working-memory one" and is now recorded on
`question-set-answered-from-memory` too.

#### Left to the developer

- **Does a body in the gripper count as an object the robot sees, or as part of
  the robot?** `AbstractRobot.bodies` includes what the robot is holding -- 10
  against the 9 in `MinimalRobot.bodies_of_branch` -- so `ObjectsSeen` no longer
  lists the held cube. The test asserts that consequence rather than hiding it.
  If it should be listed, `AbstractRobot` wants an accessor for its own links
  that a grasp cannot widen. Raised on the review thread and left open.
- **Should an episode record which links were the robot's?** Both the embodiment
  bucket's long-term spelling and the robot's own degree-of-freedom count need
  it, and recording the world does not answer it. The long-term count is
  therefore named for what it counts -- `NumberOfDegreesOfFreedomInTheRecordedWorld` --
  rather than claiming to be the robot's. Also raised on a thread and left open.
- **Should `Shape` be a symbol?** `ObjectColours` selects the shapes and reads
  the colour off them, because a variable cannot range over a shape. The fix is
  the same one `DetectionEvent` got, but shapes are per-body geometry and it is
  a heavier change than this item needs.

### `question-set-and-ground-truth` (#295), resolved 2026-09-08

The item read as healthy and was not: two review threads had been open since 13:25
that day with nothing pushed against them, and neither the item's `blockers` nor its
`notes` said so. Both were asks, not questions.

#### The converter fix the previous round had deferred

`test_long_term_questions.py` carried a `NEEDS_A_COLLECTION_JOIN` xfail on seven
tests, and the round that added it recorded the fix as "per-variable aliasing in the
translator, which is EQL work rather than this item's". The developer asked for it
here instead, so that call no longer holds; the fix is on this branch.

It is per-variable aliasing, and the shape of it is one registry: every EQL variable
is bound to the FROM element it ranges over, rather than every variable translating
to its own unaliased data access object. Three things follow, each of which was a
failing test first:

- **An owner is told apart from its members.** `World` and `Body` both map under
  `SymbolDAO`, so joining `world.bodies` produced
  `ON SymbolDAO.database_id = <association>.source_worlddao_id` — the *body's*
  symbol row. A collection's owner is now bound to an alias of its own, joined
  unrestricted into the query's one FROM chain, so the ON clause names it.
- **Two variables over one collection reach two members.** The path cache handed
  both the single element the collection was first joined under, so a condition
  relating them compared a row with itself and answered nothing. Joining a
  relationship is now separate from caching a path: a membership condition always
  joins, and only chain traversal reuses.
- **A member of one collection owns the next.** `trial.ticks` then `tick.events` is
  two hops through two variables, which is what every long-term question crosses;
  `test_membership_across_two_collections_in_turn` covers it on `World.views` then
  `Cabinet.drawers`, polymorphic in the same way `Tick.events` is.

What `contains` did before, on this shape, was a SQLite `instr()` between two
integer primary keys — string containment — with the owner never joined at all. That
is why the answer was empty rather than wrong.

krrood's ORM suite is 138 passed, from 135 passed and 1 xfailed; all three new tests
fail on the translator as it stood and pass on the fixed one.

#### `AgentInteractionEvent`, and why the mixin was the wrong shape

`ManipulatesBodies` was added in the previous round so an agency question could ask
which bodies the robot acted on. The reviewer's point is that every implementation of
it returned `[self.tracked_object]`: an event's tracked object already *is* the object
acted on, so the mixin restated `EventWithTrackedObjects` and the abstraction belonged
to coraplex's actions instead. segmind now carries `AgentInteractionEvent`, an abstract
`EventWithTrackedObjects` that `PickUpEvent`, `PlacingEvent` and `InsertionEvent`
inherit, which also matches the vocabulary the package already uses in
`AgentContactEvent`.

It has a consequence beyond tidiness: `manipulated_bodies` was a Python property, so
`contains(manipulation.manipulated_bodies, ...)` could never translate to SQL whatever
the join did. Both agency questions now compare `tracked_object`, a mapped
relationship, so the long-term agency spelling is translatable for the first time.

#### Left to the developer

Unchanged, and both still open on their threads rather than answered here, because
each changes what the representation claims rather than how it is queried: whether a
body in the gripper is an object the robot sees or part of the robot, and whether an
episode should record which links were the robot's.
### `question-set-and-ground-truth` (#295), what CI said about the round above

The round above was reported as done on the strength of krrood's own suite. CI, which is
where the long-term questions actually run, failed three of them: the join translated,
but the answers came back multiplied -- nine rows where `['cube', 'cube', 'cylinder']`
and `['cube']` were right.

Two defects, both in shapes krrood's new tests did not cover, and each a failing test
there first:

- **Selecting an attribute reached through a collection.** `entity(event.tracked_object)`
  is the shape of most long-term questions, and the variable such a chain starts from was
  never bound to what the query selects from -- only a plain selected variable was. That
  table then sat in the query with nothing joining it, so the answer was a row per pair of
  the members with every row of it, and the conditions restricting the collection's owner
  were lost with it: the reproduction returned drawers from *both* worlds, not merely too
  many of the right one.
- **A condition relating two members of one collection.** Dropped outright. Read as a
  table-level join, it resolves both sides to the members' shared data access class, finds
  that table in the query already, and reports itself handled -- a heuristic that cannot
  tell two aliases of one class apart, which is exactly what the round above had just made
  possible. A comparison whose sides both range over a bound element is now left to be
  translated as the ordinary condition it is.

krrood's ORM suite is 140 passed.

**Why the first round missed both.** Every membership test it added asserted
`sorted(names)` over rows whose names were distinct, so a duplicated row could not fail
one, and none of them selected an attribute *off* a member -- they selected the member.
The item's own note that "CI is what answers the question" was right, and the round
before this one reported the answer before CI had given it. Assert the rows a query
returns, not the set of them.
### `question-set-and-ground-truth` (#295), the third review round

Three asks, all acted on.

**The condition combiners are read off their base classes.** `CONDITION_COMBINERS` listed
`Where`, `AND`, `OR` and `Not`; the reviewer asked for the base classes instead, and
`(LogicalOperator, Filter)` is exactly that set -- `Comparator` is neither, which is what
the walk has to keep out, so the narrowing the list was doing is done by the hierarchy.
An operator added later needs no second edit here.

**coraplex's actions gained `ManipulatesBodies`.** This is the mixin the first review
round asked for, in the package it was meant for: an event's tracked object says what was
acted on after the fact, and nothing said it while the robot was acting. Nine actions
carry it -- pick-up, grasp, place, open, close and the four transport composites -- and it
normalizes the two ways they name their object, some carrying the body and others the
semantic annotation it is rooted at.

It inherits `Symbol`, and that is the part that makes it answer the developer's actual
ask ("such that we can query the actions that the robot is performing"). Measured on a
standalone mimic of the class shape rather than assumed:

```
variable(ManipulatesBodies, domain=[])   -> []
variable(ManipulatesBodies)              -> ['cube', 'cylinder']
```

-- so an explicitly empty domain is an empty domain, and a domainless variable resolves
from the graph. The same reading as `DetectionEvent` in the previous round.

coraplex cannot be installed in a session container (it needs ROS), so its test is
CI-only, like `experiments`'. What was checked here is the part that would fail at import:
that `Symbol` mixed into a dataclass with non-default fields still constructs, which it
does because `_inference_explanation_` is `init=False` and so takes no place in the
generated `__init__`.

**A new item: `objects-seen-asked-of-the-perception-system`.** `ObjectsSeen` answers from
the belief state, and the developer's point is that it should ask the perception system,
which builds a detection pipeline out of whatever the belief state says is detectable and
returns hypotheses. He asked for it as an item of its own and for the current
implementation to stay until it lands. Recorded in this plan because the question it
changes lives here, with a note on the item that icra-mechanism's `backend-routing` track
may be the better home.

#### A third defect in the same fix, again found by CI

The round before this one left two of the long-term questions failing, and the error was
not the multiplied rows -- it was `MissingColumnError` on `DetectionEventDAO`.

A membership bound its member to an alias of the class the *collection* is declared to
hold. `Tick.events` holds events; the agency question asks two of them for their
`tracked_object`, which only the events that track one have. So the variable lost the
class it was declared over, and the column it went looking for was genuinely not on the
element it had been bound to. A membership now aliases the members as the class its own
variable ranges over where that is narrower, joining through it.

The error hid itself while being raised: `MissingColumnError` read its columns off
`inspect(dao_class).columns`, which an alias does not have, so building the message threw
`AttributeError: columns` and the real failure never got printed. It goes through the
mapper now, and has its own test, because an error that fails while reporting costs a
whole CI round.

krrood's ORM suite is 142 passed.

**Both of the last two rounds were caught by CI rather than by krrood's own tests, and
both times because the shape the questions actually use was not in the dataset.** The
gap each time was polymorphism: a collection declared as a base class, holding members
the query names more precisely. `World.views` is the dataset's only such collection, and
until this round nothing asked a member of it for something only the subclass has.

#### Still with the developer

The degrees-of-freedom thread is unchanged: whether an episode records the robot's own
links, not only the world's. It is the one ask on this branch that needs a decision rather
than an implementation.
### `question-set-and-ground-truth` (#295), the fourth review round

Two asks, and one of them broke every test in two packages before it was noticed.

**A mixin that inherits `Symbol` is not a local change.** The previous round gave nine
coraplex actions `ManipulatesBodies`, which inherits `Symbol` so a query can range over
them. The repository's root `conftest.py` builds one class diagram over
`recursive_subclasses(Symbol)` in an autouse fixture, so those nine classes joined a graph
every test in the repository builds -- and coraplex's `Designator.fields` read every
dataclass field of a subclass out of `get_type_hints(cls.__init__)`. `Symbol`'s
`_inference_explanation_` is `init=False`, so it has no hint there, and looking it up
raised `KeyError` while the fixture was being set up: **437 errors in coraplex, 282 in
experiments, every test in both**, and the "Examples and Demos" workflow red for the first
time on this branch.

The fix is that a designator reports the parameters its constructor takes rather than every
field it inherits, which is what both readers of it want anyway -- a plan node printing a
node's parameters, and an action making one query variable per parameter. Neither wants a
field a base contributes for its own bookkeeping. Reproduced in a standalone mimic of the
class shape first, since coraplex needs ROS and cannot run in a session container.

**Three CI rounds in a row were spent on consequences of enrolling a class in `Symbol`,**
and the reusable lesson is the one above: inheriting `Symbol` puts a class into a
process-wide class diagram and a process-wide instance graph, so it is measured against
every package that imports it rather than against the one being edited.

#### Recording the robot: the previous round had this wrong

The open thread asked whether the episode should record which links were the robot's, and
the previous round answered that recording the world does not tell a link from a grasped
body. That was wrong about the recording. The robot **is** a semantic annotation,
`World.semantic_annotations` is a mapped field, and semantic_digital_twin's own
`test_hsrb_world` already round-trips an HSRB out of the database -- so `Episode.world`
carries every annotation including the robot. `test_the_recorded_world_names_the_robot_among_its_annotations`
now proves it here rather than leaving it a claim.

Two things still stand between that and the robot's own joint count, and both are the
developer's calls rather than this item's work:

- **No run sets `Episode.world`.** `Episode.from_run` is given only the scenario, the
  scenario builds a world per trial, and `ScenarioRunner.run_trial` releases that world in
  a `finally` before it constructs the `Trial` the recorder is handed. Keeping it means
  `Trial` carrying the world it ran in and the run loop holding it past `release_world` --
  the runner's code, and it needs the one-world-per-episode-or-per-trial decision
  `Episode.world`'s own docstring left open.
- **The robot's own count is not one query.** The live spelling counts the degrees of
  freedom of active connections between two of `robot.bodies`, and
  `SemanticAnnotation.bodies` is a Python property that walks the annotation's fields.
  There is no mapped path from an annotation to its entities -- the
  `WorldEntity._semantic_annotations` backreference is private and unmapped -- so over
  recorded rows it is either a mapped relation in semantic_digital_twin or a
  recall-then-count in Python, the way `ground_truth` already reads recorded objects.

So `NumberOfDegreesOfFreedomInTheRecordedWorld` still counts the world's, which is what its
name says.


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

### `question-set-and-ground-truth` (#295): merged into #265, 2026-09-09

Merged into `integrated-simulation-pipeline` (#265). The one substantive conflict of this
session's convergence was here - `segmind/datastructures/events.py`'s new
`AgentInteractionEvent` meeting `PickUpEvent`/`PlacingEvent`/`InsertionEvent`'s existing
`EventWithEffect`/`ComesToRestEvent` - resolved by multiple inheritance rather than by
choosing a side, since the two are orthogonal classifications of the same event and
`AgentInteractionEvent` adds no fields. See `integrated-simulation-pipeline`'s entry above
for the verification.

### `paper-figures-from-episodes` (#297): merged into #265, 2026-09-09

Merged into `integrated-simulation-pipeline` (#265), cut off #278's tip as its own notes
recorded. One conflict in `generate_orm.py`, purely additive (the paper-table
`ignored_classes` loop beside the question-model one) - resolved by keeping both. See
`integrated-simulation-pipeline`'s entry above.

### `question-set-answered-from-memory` (#304), as planned 2026-09-09

Lane 3's second item to open a branch, kicked off in `auto` mode.

**Cut off #265 (`claude/icra-experiments-simulation-pipeline-w4ep7n`), not off `tracy_icra`.**
Today's structural change above says new work is cut off `tracy_icra`. Checked before cutting
anything: `git merge-base --is-ancestor origin/tracy_icra origin/pr265` holds and the reverse does
not, so `tracy_icra` is an ancestor of #265 rather than the other way round — the merge of #265
into `tracy_icra` (`tracy-demo-takes-the-integrated-branch`, `icra-foundation`, not_started, needs
the robot) has not happened yet. Basing on `tracy_icra` today would start this item with none of
`question-set-and-ground-truth`'s (#295) frozen `Question`/`QuestionSet`/`LongTermMemory` machinery,
which landed on #265. Put to the developer before cutting the branch: confirmed #265 already
carries everything `tracy_icra` does, so building on #265 loses nothing and gains the dependency.
This branch will need rebasing onto `tracy_icra` once that merge lands, the ordinary cost of a
stacked branch whose parent hasn't reached the trunk yet.

**What #295 already built, and what is genuinely left.** #295 froze `Question`, `QuestionSet`,
`WorkingMemoryQuestion`/`LongTermMemoryQuestion`, `LongTermMemory.answer`, and proved (through three
CI rounds) that the long-term half translates. What it did not build is anything that *scores* an
answer against ground truth and *records* the outcome — every existing test asserts equality
directly in Python and throws the result away. This item is that harness, plus what
`paper-figures-from-episodes` (#297) left unstubbed: "the figure the accuracy tables need is a
`PaperFigure` subclass, and adding it belongs to the item that adds the column it reads."

**One class, extended rather than duplicated.** `RecordedQuery` (`episodes/episode.py`) grows three
optional fields — `bucket`, `bloom_level`, `answered_correctly` — `None` for an ordinary query and
set for one answering a question of the frozen set. The item's own notes say a question's answer is
"recorded as an episode row like any other query," which is a second `RecordedQuery`-shaped class
would contradict — one name, one operation, per `AGENTS.md`.

**`QuestionSet.answer_and_record(source)`** asks every question of the set, times each with
`time.perf_counter`, compares its answer against `ground_truth(source)` and returns the scored rows.
Compared as sets after `Question.distinct`, not as ordered lists — a question's own order is not
something `ground_truth` commits to, and `distinct` already exists for exactly the "one row per
witness" accounting `Question`'s own docstring describes. Recorded here as a design call rather than
assumed silently.

**Two new figures**, `AccuracyByBucket` and `AccuracyByBloomLevel` in a new `paper/questions.py`,
built the way `QueryDeterminism` measures agreement: `self.indicators` over the rows that carry a
bucket/level, skipping the `None` ones an ordinary query would have. Two new `FigureName` members,
registered in `FigureSet.for_the_paper`.

**Both halves scored, not one.** The working-memory half against the scene #295's `test_questions.py`
already builds (a two-arm robot, a table, a cube and a cylinder on it, a second cube in hand); the
long-term half against one recorded episode through `open_recording`/`ResultsDatabase`, the shape
#295's `test_long_term_questions.py` already builds. CI-only for the long-term half, per the standing
ROS/generated-ORM limitation this track has carried throughout.

**Two blockers cleared as stale, one corrected.** The item's recorded blocker named
`episodes-queried-by-eql` (#278) as `in_progress` — it merged into #265 on 2026-09-09 (see the fast
convergence above), and this item is cut from that same base, so the dependency is satisfied through
it rather than argued as a `depends_on` edge. `episode-corpus-generated-at-scale` (not_started) is
not actually needed: this item scores the frozen set against one scene and one recorded episode, the
same scale #295's own tests already run at, not a corpus at scale. `integrated-simulation-pipeline`
(#265) is what this item is cut from, so it is satisfied by the base rather than a separate edge.

**Left as #295 left it, out of scope here.** The control bucket (both spellings), spatial relations
over long-term memory, and embodiment over long-term memory / the robot's own long-term
degree-of-freedom count have no spelling to score yet; the accuracy tables report what exists rather
than stub the rest.

#### Testing

TDD throughout: a failing test proving `answer_and_record` produces a scored `RecordedQuery` before
the method exists, and a failing test per new figure before it exists. `test_questions_answered_from_memory.py`
for the working-memory half, run locally against a real twin; a long-term counterpart CI-only,
recording one episode of two trials the way `test_long_term_questions.py` does and asserting the
regenerated `AccuracyByBucket`/`AccuracyByBloomLevel` figures over it.

Session: https://claude.ai/code/session_01CeBaw39xNxHaYphUsVzXow

### `question-set-answered-from-memory` (#304), as built 2026-09-09

What was implemented against the plan above, and one open question found while
building it that stands between this and a trustworthy long-term-memory accuracy table.

**Built, matching the plan exactly.** `RecordedQuery` grows `bucket`/`bloom_level`/
`answered_correctly`, all `None` for an ordinary query. `QuestionSet.answer_and_record`
asks every question of a set, times each with `time.perf_counter`, and scores it. Two
new figures, `AccuracyByBucket` and `AccuracyByBloomLevel` (`experiments/paper/questions.py`),
report the tables `paper-figures-from-episodes` (#297) left unstubbed, registered in
`FigureSet.for_the_paper`. `generate_orm.py` gained the new module in its ignore list --
a question is asked, not recorded, same reasoning as every other `questions`/`paper` module
already there.

**`Question.values_agree`/`matches_ground_truth`, promoted out of `test_questions.py`
rather than duplicated.** The comparison `answer_and_record` scores against is exactly
what `test_questions.py`'s own `answers_agree` free function already did (numeric for a
`SpatialType`, position-by-position for a list, `==` otherwise) -- introducing the same
logic a second time in production code would have been the exact duplication `AGENTS.md`
rules out, so the method moved onto `Question` itself and the test file now calls it
instead of carrying its own copy. Three of that file's own tests, and the "every question
of the set" one, now read `question.matches_ground_truth(robot)`.

**An open question, not resolved here: the long-term half compares list answers
differently, and `values_agree` does not yet know that.** Re-reading
`test_long_term_questions.py` closely before writing a long-term-memory test of my own
found that its "every question at once" test does *not* use a position-by-position
comparison for a list-valued answer -- it sorts both sides by name first
(`names(answered) == names(true)`), and every other long-term test asserting a list
answer does the same (`ObjectsSeenInTheEpisode`, `ObjectsThatMovedInTheEpisode`,
`ObjectsTheRobotMovedInTheEpisode`). The working-memory half's own test never sorts.
That is a real, already-established difference between what "correct" means for the two
memories' list-valued answers, not an inconsistency I am choosing to invent a fix for:
either the long-term backend's row order is not guaranteed to match ground truth's
traversal order (in which case `values_agree`'s zip comparison would mark a right answer
wrong whenever the database returns rows in a different but equally correct order,
undercounting the long-term accuracy table), or the sorted comparison was only ever a
convenience and position happens to agree too. I do not know which, and guessing would
risk exactly the kind of scoring bug this track has already paid three CI rounds to find
on #295 -- so this is left to the developer rather than resolved by assumption.

**Consequently, no long-term-memory test of `answer_and_record` is added on this
branch.** The method itself is memory-agnostic and already works unchanged for
`QuestionSet.over_long_term_memory(...).answer_and_record(long_term_memory)` -- nothing
long-term-specific was written -- but a test that can't be trusted to fail for the right
reason is worse than no test, per the same lesson #295's own roadmap already records
("assert the rows a query returns, not the set of them"). Whoever answers the question
above can add the long-term counterpart test in an hour once `values_agree`'s list case
is fixed, if it needs fixing.

**Neither half was run in this session's container.** `uv sync` fails outright with a
`pyproject.toml` parse error unrelated to this branch (`docopt-ng`'s dependency entry at
line 72 is a table, which this container's `uv` 0.8.17 rejects as "expected a string
containing a PEP 508 requirement") -- so the workspace could not be installed here at
all, working-memory half included, unlike #295's own session which reported running 20
tests against a real twin. CI is what verifies both halves on this branch; the tooling
issue is reported here rather than fixed, since it is a pyproject.toml/`uv` version
mismatch on the base branch and unrelated to this item.

#### Testing

`test/experiments_test/test_question_scoring.py`: `answer_and_record` scores every
working-memory question of #295's own built scene, asserting each row's text/bucket/
bloom_level/correctness against the question it came from; the two new figures are
tested in memory the way `test_paper_figures.py` already tests every other figure,
including that an ordinary (unscored) query is excluded from both tables. Not run
locally, for the container reason above; CI is what verifies it.

Session: https://claude.ai/code/session_01CeBaw39xNxHaYphUsVzXow

### `question-set-answered-from-memory` (#304), reviewed 2026-09-09

Two rounds: CI came back broadly red on the first push, and the developer left two
review threads. Both are resolved.

**CI's dominant failure was #265's, not this item's, and was fixed there.** Nearly every
test that executes a simulated motion failed with `AttributeError:
'GiskardExecutable' object has no attribute 'is_paused'`. Traced to `tracy_icra`'s own
`GiskardExecutable` having `is_paused`/`is_interrupted` (delegating to each motion
mapping's `PlanNode`) that were silently dropped when tracy_icra merged into #265 -
`main` never had them either, so it was not a main-merge casualty. Restored on
`claude/icra-experiments-simulation-pipeline-w4ep7n` directly, with a unit test, and
merged into this branch so #304's own CI picks it up too; see
`integrated-simulation-pipeline`'s own roadmap entry for that fix. A second, unrelated
failure (`test_generation_needs_no_ros_message_package`, caused by a *generated*
`ormatic_interface.py` file pulling in a ROS message import) is pre-existing on #265 and
left to the developer, per `AGENTS.md`'s rule against touching generated ORM files.

**Both review threads asked the same thing: a reference to the `Question` class, not a
duplicated field.** One on `question_set.py`'s `RecordedQuery` construction ("can't
RecordQuery be a Role for a Question... or a reference field to the question class...
not the instance"), pointing at `Question`'s own field block in #265's diff as the
"sibling class" meant; one on `test_paper_figures.py`'s `query()` helper ("take the
actual Question object... or the Question SubClass? I guess a class object is
serializable or recordable, right?"). Not a `Role[Question]`: a role holds a live
reference to its role taker, and a `Question` instance does not survive past the process
that asked it, which is exactly why `generate_orm.py`'s ignore list excludes `Question`
from ORM mapping in the first place.

**`RecordedQuery.bucket`/`bloom_level` (two persisted fields) are replaced by
`question_type: Optional[Type[Question]]`** - the class object itself, not an instance.
`bucket` and `bloom_level` are now read-only properties reading
`question_type.bucket`/`question_type.bloom_level`, both `ClassVar`s already on
`Question`, so the two can no longer be given independently and drift apart. This needed
no new ORM machinery: ORMatic's `TypeType` decorator (`krrood/ormatic/custom_types.py`)
already stores any `Type[X]` field as `module.ClassName` and resolves it back, wired
into `type_mappings` for bare `type`/`Type` regardless of `X`, and already exercised
end-to-end by `KRROODPositionTypeWrapper.position_type: Type[KRROODPosition]` in
krrood's own `test_ormatic/test_interface.py`.

`question_set.py`'s `answer_and_record` passes `question_type=type(question)`.
`test_paper_figures.py`'s `query()` helper takes `question_type: Type[Question] | None`
instead of separate `bucket=`/`bloom_level=` keywords; `text` stays a separate parameter,
since `english` is an abstract *instance* property (`AnythingMovedInTheEpisode` needs its
own `episode_identifier` to render it), so there is no class-level text to read without
constructing one. `test_question_scoring.py`'s scored corpus now references the real
classes it was standing in for (`ObjectsSeen`, `ObjectColours`,
`AnythingMovedInTheEpisode`) instead of independently-chosen bucket/level combinations -
exactly the drift the reviewer was pointing at. `figure.py`'s `scored_queries_of` and
`paper/questions.py`'s two figures needed no change: both read `query.bucket`/
`query.bloom_level`, which now resolve through the properties transparently.

Neither half was run locally, for the same container reason as every round on this
branch; formatting was still run, via a throwaway venv built to hold black/docformatter/
tqdm since `uv sync` itself fails here.

### `question-set-answered-from-memory` (#304), reviewed again 2026-09-09

Two more comments landed on the same field minutes after the round above: "why is it
optional? This should replace the text field as well, and be a required field", then
"Actually, I think this must be a Role[Question], and find a clean way to solve the
ormatic issue... maybe use `AlternativeMapping`... as a last resort".

**A mechanism already in ORMatic solved it without `Role` or `AlternativeMapping`.**
`ormatic.py` already sets `type_mappings[SubclassJSONSerializer] = JSON`, and `TypeDict`
resolves a field's mapping by nearest inheritance distance - so any class inheriting
`krrood.adapters.json_serializer.SubclassJSONSerializer` gets a JSON column
automatically. `Question` now inherits it, delegating `to_json`/`_from_json` to the
already-existing generic `DataclassJSONSerializer` (which introspects a dataclass's own
fields and skips `ClassVar`s) - two methods, not new infrastructure, and exactly the
reuse AGENTS.md already asks for rather than hand-writing serialization.

**The round above's fix was not just less than what was asked - it was wrong.**
Re-reading `long_term_memory.py` while investigating found `episode_identifier: str` is
a real per-instance field on every `LongTermMemoryQuestion` (which run the question is
about). `RecordedQuery.question_type: Optional[Type[Question]]` stored only the class,
silently discarding that - a recorded long-term answer could not say which episode it
was actually asked of. `question_type` is now `question: Optional[Question]` - the
instance that was asked, not its class - which is what makes this a correctness fix, not
only a persistence one. Verified against a standalone mimic reproducing `Question`'s
exact shape, since this container still cannot import the full `experiments` package
(`casadi` and the rest); two real tests added in `test_questions.py`
(`ObjectsSeen`/`AnythingMovedInTheEpisode`) for CI to verify end to end.

**One part of the ask left unresolved, flagged rather than guessed at.** Making
`question` required and dropping `text`, as literally asked, conflicts with
`QueryDeterminism` (`paper/queries.py`, already merged in #297): it groups *any*
recorded query - not only ones answering a frozen-set question - by its literal `text`,
and its own tests (`test_paper_figures.py`) exercise plain ad hoc EQL queries with no
`Question` behind them at all. Making `question` required would mean either giving
`Bucket`/`BloomLevel` a "not part of the frozen set" member - touching a taxonomy #295
already froze and reviewed four rounds on - or breaking that shipped feature. Kept
`question` optional and `text` in place; replied on the thread with the concrete
conflict and asked which he wants, per the standing rule against resolving a thread
whose ask was answered differently from what it asked.

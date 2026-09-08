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

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

**Every item in this plan except `benchmark-artifact` depends on at least
one item in `icra-foundation` or `icra-mechanism`** (ten of this plan's
eleven items carry a cross-plan `blockers` entry instead of a `depends_on`
edge, since `depends_on` cannot cross a plan boundary — see plan.yaml). Read
`icra-foundation`'s roadmap first for the programme's overall "why"; this
file states only what is specific to this wave.

## Why this wave exists

The memo's evidence is experiments on the UR10, each run end to end in
simulation first: **A**, question answering in four buckets (lookup,
spatial, temporal, embodiment) against a VLM with and without verbalised
working memory; **B**, per-predicate backend decomposition of a mixed query
plus a perceive-commit-verify loop under injected errors; **C**, insertion
under knowledge ablations and perturbations, every failure typed and
predicted; and **D** (added 2026-09-04, see below), the same four buckets
asked of the recorded episode history rather than the current scene. The
`release` track packages what all four produced.

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

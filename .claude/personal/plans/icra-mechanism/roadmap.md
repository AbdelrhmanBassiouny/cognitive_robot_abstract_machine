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

**Every item in this plan depends on at least one item in `icra-foundation`
or `icra-evidence`** (nine of this plan's twelve items carry a cross-plan
`blockers` entry instead of a `depends_on` edge, since `depends_on` cannot
cross a plan boundary — see plan.yaml). Read `icra-foundation`'s roadmap
first for the programme's overall "why"; this file states only what is
specific to what this wave measures.

## Why this wave exists

The memo's thesis is one mechanism: the same EQL query selects which backend
answers each predicate, drives what the robot perceives, and verifies the
result in the digital twin; removing knowledge produces failures the query
predicts. This wave builds that mechanism and its supporting pieces:
per-predicate backend routing (`backend-routing`), physics verification
(`backend-routing`), snapshot working memory (`backend-routing`), typed and
predicted failure with the ablations/perturbations that produce it on
purpose (`failure`), and the verbalised-memory/VLM baselines the experiments
compare against (`baselines`).

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

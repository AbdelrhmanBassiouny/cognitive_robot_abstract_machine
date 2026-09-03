# icra-experiments: roadmap

The narrative half of `plan.yaml`: why the plan has the shape it has, what it
was built on, how the work is distributed, and the day-by-day budget to the
2026-09-15 deadline. Created 2026-09-03 from the review of the ICRA planning
memo (`icra_plan.tex`, dated 3 September) against every tracked plan, the open
pull requests and the `tracy_icra` demo branch.

## What the memo asks for that no plan owned

The memo's thesis is one mechanism: the same EQL query answers a question,
selects which backend answers each predicate, drives what the robot perceives,
and verifies the result in the digital twin; removing knowledge produces
failures the query predicts. Its evidence is three experiments on the UR10:

- **A**, question answering on the real feed in four buckets (lookup, spatial,
  temporal, embodiment), against a VLM with the image alone and a VLM with the
  image plus verbalised working memory, with determinism runs.
- **B**, per-predicate backend decomposition of a mixed query with measured
  narrowing, and a perceive-commit-verify loop under about thirty injected
  errors with precision and recall.
- **C**, insertion under knowledge ablations and a perturbation, every failure
  typed and predicted before execution.

Of the twenty plans tracked on 2026-09-03, only `knowledge-directed-perception`
carried the deadline, and it owns perception: the surfaces, the perception
backend, the detector rule tree, expectations from events. Nothing owned the
experiments, the scenario definitions, the episode recording, the capability
routing across backends, the physics verification, the failure taxonomy, the
VLM baselines or the artifact. This plan owns those.

## What the code already had, and what this plan builds on

Recorded so that no item rebuilds it:

- **Narrowing is measured.** #238 narrows a look by a whole statement and
  reports per-frame cost of 0.25 to 0.43 of an unnarrowed look on the six real
  captures. Experiment B's decomposition half extends that measurement rather
  than starting it.
- **Decomposition exists implicitly.** In #238 the lid and the hole named in a
  statement are answered from the twin before any look is taken, and #222
  splits every condition into pushed down, residual or refused. #231 has each
  detector declare the looks it can answer as an EQL condition. The
  `backend-routing` track raises that one level: backends declare
  capabilities, a planner routes per predicate, and the routing is reported.
- **The verification predicates exist.** #229 made support, contact,
  visibility, reachability, stability, occupancy, inside-of and the six
  directional relations into predicates with a measurement behind each. The
  demo already settles shapes in MuJoCo. `physics-verification-backend` is
  those predicates evaluated in a copy of the world.
- **Episode recording exists in three shapes.** `ShapeInsertionExperience`
  with `generate_insertion_experience` and `batch_runner`,
  `SortingIterationResult` with `ResultsDatabase` and `results_recording`, and
  the console stack's `SegmindEventRecord` and `InsertionAttemptRecord`. All
  go through ORMatic into SQL already. `episodes-recorded-through-ormatic`
  replaces the first two with one Episode model and keeps the database
  plumbing.
- **A scenario abstraction and a result model exist.**
  `control_loop_experiments.scenarios` has `BenchmarkScenario` and
  `ScenarioRunner`; `experiment_definitions` has `ExperimentResult`,
  `ExperimentsTable` and `TypstRenderer`. `scenario-domain-model` generalises
  both rather than adding a third.
- **Failure diagnosis exists.** `insertion_diagnosis.InsertionDiagnosis` and
  `InsertionFailureReason` already read an attempt's failure from the plan's
  own failure and the segmind events. `failure-taxonomy-and-typing` maps each
  reason to one of the memo's four types.
- **The temporal and embodiment answers have sources.** Segmind emits support,
  loss of support, pick-up, placing and insertion events, detected by EQL
  rules (not ripple-down rules, which the developer corrected on 2026-09-03).
  The twin answers what is in the gripper through `bodies_in_gripper`. The
  console stack's `live_query_source` already has presets for "what actions
  did you perform" and one question per event type.
- **Attach on grasp exists.** #169 restored `AttachNode` and `DetachNode`
  behind `Context.update_world_model_attachment`, so a grasped shape moves
  with the gripper in the twin. `snapshot-working-memory` relies on it rather
  than rebuilding it.
- **Verbalisation is deterministic by construction.** The result-verification
  framework is on main; the scene wordings are on #33, which owes a rebase
  onto #229 and has two wording decisions only the developer can settle.

## Corrections the developer made on 2026-09-03

- **SQL is a backend, and long-term memory is a deliverable.** The first
  review read SQL as present only in the console stack; the developer's
  direction is that EQL over an SQL database returning domain objects is the
  long-term memory feature, that episodes of every scenario, real and
  simulated, are recorded through ORMatic into it, and that they are to be
  queried. The `long-term-memory` track exists for that, and the memo's four
  backends stand.
- **Simulation first.** Every scenario, demo and perturbation runs through the
  full integrated pipeline in simulation before the robot, to save robot time
  and remove surprises. This is why every experiment has an in-simulation item
  that its robot item depends on, and why `integrated-simulation-pipeline` is
  the foot of the plan.
- **Scenarios are data.** A dataclass domain model describes scenarios, goals,
  conditions, perturbations and metrics at a meta level; each concrete scenario
  subclasses or instantiates it. Everything tested and running.
- **#192 is the developer's.** He is fixing or has fixed it; the integration
  item keeps it out until he says it is in, because it removes
  `Match.variable`, which #159 and so #239 still read.
- **Segmind uses EQL rules**, not ripple-down rules.

## Structural decisions taken at creation

Asked and answered by the developer on 2026-09-03:

- The two core mechanisms (per-predicate routing by declared capability, and
  the physics verification backend) live here, in the `backend-routing`
  track, not in `knowledge-directed-perception`. That plan's
  `imagination-world-rejects-what-a-predicate-refuses` item is covered by
  `physics-verification-backend` in its narrow form and should be marked so
  there rather than built twice.
- The integrated simulation pipeline is this plan's foot item. `tracy_icra`
  stays the real-robot integration point and takes the integrated branch;
  `knowledge-directed-perception`'s three demo items are satisfied by
  `tracy-demo-takes-the-integrated-branch` and the robot experiments.
- Three lanes, one per person, below.

## The three lanes

Each lane is one person's ordered list. Items in different lanes run in
parallel; an item waits only on what `depends_on` names.

**Lane 1, robot, perception and mechanisms.**
`integrated-simulation-pipeline` → `simulated-camera-feeds-perception` →
`backends-declare-their-capabilities` → `query-routed-per-predicate` →
`physics-verification-backend` → `snapshot-working-memory` →
`tracy-demo-takes-the-integrated-branch` → `experiment-b-in-simulation` →
the three robot runs, with lanes 2 and 3 at the table.

**Lane 2, experiment infrastructure and long-term memory.**
`scenario-domain-model` → `episodes-recorded-through-ormatic` →
`montessori-scenarios` → `failure-taxonomy-and-typing` →
`knowledge-ablations` → `perturbations` → `episodes-queried-by-eql` →
`failure-predicted-from-the-query` → `experiment-c-in-simulation`.

**Lane 3, baselines, question set, figures and writing.**
`question-set-and-ground-truth` → `working-memory-verbalised` →
`vlm-baseline-harness` → `paper-figures-from-episodes` →
`experiment-a-in-simulation` → `benchmark-artifact`, writing the paper's
sections 1 to 4 in the gaps and the experiments section from the generated
tables.

## The budget: 2026-09-15

Twelve days from 2026-09-03. The memo's own timeline is kept where it holds
and moved where the plans showed it could not: the memo's day one asked for a
decomposition prototype and attach-on-grasp, both of which exist, and did not
ask for the integrated simulation pipeline, which is what everything else
waits on.

| when | lane 1 | lane 2 | lane 3 | state reached |
|---|---|---|---|---|
| Thu 3, Fri 4 | integrated pipeline; simulated camera | domain model; episodes recorded | question set frozen; memory verbalised | **the simulated demo runs the whole pipeline and records episodes** |
| Sat 5, Sun 6 | capabilities; routing | scenarios; taxonomy; ablations; perturbations | VLM harness; figures script | **go/no-go Sunday evening: routing and physics verification answer a mixed query in simulation** |
| Mon 7, Tue 8 | physics verification; snapshot memory; tracy takes the branch (robot Tue) | episodes queried; prediction; Experiment C in simulation | Experiment A in simulation | **every experiment has run once in simulation** |
| Wed 9, Thu 10 | Experiment B in simulation, then robot A | robot C | robot A ground truth, tables | robot numbers for A and C |
| Fri 11 | robot B | reruns | experiments section | full first draft |
| Sat 12, Sun 13 | video | reruns | artifact; internal review | reviewed draft, artifact |
| Mon 14, Tue 15 | | | tighten, limitations, submit | submitted |

If the go/no-go fails, the memo's fallback holds: submit with A and C and
drop B's injection half, keeping the decomposition numbers from #238.

**Cut order**, from the memo and unchanged: lighting → the optional
no-narrowing ablation → a second setup → fewer random scenes → B's injection
half. Never cut: the temporal scenarios, the perturbation conditions, the
hybrid VLM baseline, the failure-prediction metric, the determinism runs.

## Cross-plan prerequisites

Decided on 2026-09-03: work the paper needs that another plan already owns
stays in that plan, and the item here that needs it carries a blocker naming
it. What the deadline still needs from each plan:

- **knowledge-directed-perception.** Everything in its `surfaces`,
  `request-language` and `method-selection` tracks that is built (#202, #205,
  #216, #221, #222, #225, #227, #229, #231, #232, #236, #238, and #239's
  knowledge-half commit) is consumed by `integrated-simulation-pipeline`; the
  paper does not wait for those pull requests to land. Still needed and not
  started there: `expectations-from-events`, which is the failure-detection
  story and blocks `failure-taxonomy-and-typing`'s expectation-derived type
  and `experiment-c-in-simulation`. Its three demo items are satisfied by
  `tracy-demo-takes-the-integrated-branch` and the robot experiments here,
  and its `imagination-world-rejects-what-a-predicate-refuses` item is
  covered in narrow form by `physics-verification-backend`. Not needed for
  the paper: `competing-explanations`, `how-to-look-concluded-from-the-request`,
  `surfaces-found-by-looking`, `tune-detection-rules-against-the-camera`,
  `robokudo-detector`, the rule-tree half of #239, and
  `episode-replayed-into-the-world` (#246) unless a recording has to be
  replayed for the temporal questions.
- **montessori-eql-stack.** #244 and #256 are merged into the integrated
  pipeline; #169 is not, since 2026-09-03 - #256 carries the monitor, the grasp
  attachment and the recording, split out of #169 so the paper need not take the
  cramera console. What is left of #169's debt here is the unbounded
  `SimulationTimePacer.sleep()`, and that plan owns it. The console stack above #169 (#170, #164, #165, #167,
  #168) is not needed for any number in the paper; #168's presets are reused
  by `question-set-and-ground-truth` as EQL text only. The video may want the
  console; that is a 12 to 13 September decision.
- **eql-verbalization.** #33's reviewed scene wordings are what
  `working-memory-verbalised` renders with; the item does not wait for #33 to
  rebase or land. The two wording decisions open on #33 are the developer's.
- **Not on the deadline path:** eql-performatives, eql-existential-semantics,
  match-query-ergonomics (#192 is the developer's own), the rdr-* plans, and
  every tooling plan.

## What this plan takes priority over

Until 2026-09-15, the following in-flight work waits unless it unblocks an
item here: the console UI items of `montessori-eql-stack` (#176, #177, #180,
the written-action and detachable-panel items), `eql-performatives`,
`eql-existential-semantics`, the `rdr-explanation` demo,
`knowledge-directed-perception`'s `tune-detection-rules-against-the-camera`,
`how-to-look-concluded-from-the-request`, `surfaces-found-by-looking` and the
rule-tree half of #239, and `competing-explanations` unless Experiment A's
false positives force it.

## Memo corrections this plan carries

Things the memo states that the code contradicts, to be fixed in the memo
and the paper rather than worked around:

- There is no in-hand event and no Flanagan model. In-hand is a twin
  predicate; the pick-up detector is an EQL-rule detector over contact and
  support.
- The board mesh is 0.865 times the real board (#236). Ground truth from the
  twin and the no-hole-shape-knowledge condition both need the scale in the
  twin first.
- Only one of the six recordings carries robot state. Every future take
  records the transform tree and joint states with the camera.
- The continuous perception node cannot hold the frame budget once the hole
  layout fit runs (0.56 s against 0.5 s); the snapshot design is what makes
  that irrelevant.

## Open questions for the developer

- Which vision-language model and provider the baseline harness calls, and
  whether the credentials can be in CI (they need not be; the live test is
  skipped without them).
- Whether `knowledge-directed-perception`'s `expectations-from-events` is
  still needed for the paper once `snapshot-working-memory` and
  `failure-taxonomy-and-typing` exist, or whether the violated-expectation
  report folds into the failure typing here.

## 2026-09-03: the foot item takes #256, not #169

`integrated-simulation-pipeline` merged `montessori_fast_inline_monitor` (#169) for three
things: the segmind event monitor, the attach/detach of a grasped shape behind
`Context.update_world_model_attachment`, and the results recording. #169 had meanwhile
become the cramera console — **164 of its 272 files** — so taking those three meant taking
the viewer, its CI surface and its review.

They are their own pull request now: **#256 `montessori_monitor_and_recording`**, between
#244 and #169 in stack #258. 35 files, and nothing in it imports `cramera`. The merge
order in this item's notes names #256 in #169's place; nothing else about the item
changed.

Three wrong-direction imports had to be straightened for that to be true, all on the
`montessori-eql-stack` side: `MethodPatch` moved out of cramera to
`krrood.patterns.method_patch`; `sorting_progress` reads `NumericPose` from
`semantic_digital_twin.spatial_types.numeric`, where it is defined, rather than from
cramera's re-export; and the one test that drives a monitor into
`MontessoriLiveEventSource` stayed with that adapter. That plan's roadmap carries the
detail.

### What stays in #169, and why this item does not need it

`franka_montessori_demo.py` and the three cramera adapters. `SortingRunControl` subclasses
cramera's `LiveRunControl` ABC and its clock is `cramera.live.run_clock.RunClock`, so the
demo entry point cannot cross without inverting that layer — scoped, and deliberately not
done.

It is not needed, and checking that is what settled the cut: **`tracy_icra` has no cramera
and carries its own `montessori_demo.py`.** So this item's "sorts the board headless" is
met by that demo, not by `franka_montessori_demo`. Worth knowing for the meetings this
item already plans to resolve: `tracy_icra` built its own `experiments/montessori/`
package, and so did #169 — the directory exists on neither `main` nor #244, so the two
packages meet here in full, not in a few files.

### The blocker this item carried is down to one line

It named three coraplex failures, a hanging Tracy demo job and an unbounded
`SimulationTimePacer.sleep()`. The first two are fixed — the gripper round (`7fa4b1936`)
cleared them, and all 24 checks passed on #169's `c8bf6f05`. Only the unbounded `sleep()`
stands, and it is a policy question rather than a bug to guess at: no test reaches it,
only the demo scripts set `context.simulation_clock`, but a stalled simulation blocks a
tick forever.

## 2026-09-03: what the scenario domain model is, and what migrates onto it

`scenario-domain-model` (#261, off `main`, no dependencies) settled on this shape,
drafted from the item's own notes and from what `control_loop_experiments` and
`experiment_definitions` already do.

**The model**, in `experiments/src/experiments/scenarios/`:

- `Scenario` builds its world, names its ordered steps, carries its `Goal` and says
  whether it runs simulated or on the robot (`ExecutionKind`, defaulting to simulated,
  because the plan runs every scenario in simulation first). Which robot it runs on is
  the second bound generic parameter, read back through `SubClassSafeGeneric`, so the
  robot is part of the type rather than an attribute that can disagree with it.
- `Goal` answers whether the trial succeeded, from the world the trial finished in.
- `Condition` switches one knowledge source off before a trial runs, so an ablation is
  never a code branch inside an action.
- `Perturbation` names the step it is applied at and the change it makes to the world.
  A step is identified by a member of the scenario family's own `StepName` enum, so
  neither the runner nor a perturbation carries a step spelled as a bare string.
- `Metric` reads one number off a finished `Trial`; `Report` gathers a metric over the
  trials as a mean, a standard deviation and a `ConfidenceInterval`.
- `ScenarioRunner` runs the trials: build the world, apply the conditions, perform each
  step with the perturbations due at it, ask the goal for the outcome, and record every
  one of those as a typed entry of the trial's log.

**Decisions taken while drafting it:**

- *Conditions and perturbations belong to a run, not to a scenario.* The runner takes
  them per run, so the same `Scenario` is what Experiment C runs under every ablation
  and what Experiment A runs unablated. `knowledge-ablations` and `perturbations` add
  members, not a second scenario each.
- *The trial log is structured objects, not text.* One class per kind of entry, each
  carrying its own subject, so `episodes-recorded-through-ormatic` maps them rather than
  parsing them back out of a string. Nothing here writes them to a file or a database:
  that is that item's, and this one only builds the record.
- *The report is rendered by what already renders the experiments.* `Report` produces
  `ExperimentResult` rows into an `ExperimentsTable` and renders through `TypstRenderer`;
  `ConfidenceInterval` joins `MeanAndStandardDeviation` in `experiment_definitions`
  rather than starting a second reporting vocabulary in the new package.
- *The confidence interval is the normal approximation of the mean's standard error*,
  built on `statistics.NormalDist` the way `free_space_volume_estimation`'s Wilson-score
  interval already is. The Wilson interval stays where it is: it bounds a proportion, it
  has its own tests, and moving it would be an unrelated refactor.
- *The new classes stay out of the experiments ORM generation*, alongside the
  control-loop scenario modules that are already ignored there. What of a trial and its
  log becomes a mapped record is `episodes-recorded-through-ormatic`'s call, not a side
  effect of adding the model.

**What migrates onto it:** `BenchmarkScenario` becomes a `Scenario`, keeping its seed
configuration, its world preparation and its motion statechart, and the control-loop's
own `ScenarioRunner` becomes a subclass of the model's runner that measures the control
loop while the motion step runs, so one name means one operation across the workspace.
The plotter mode and target frequency move from the runner onto the scenario, which is
where "how to build the world" now lives.

**A caveat worth knowing at review time:** the control-loop tests that actually drive a
runner are `@pytest.mark.slow`, and the default CI selection is `-m "not slow"`, so CI
proves that the migrated benchmark imports, collects and aggregates, not that it still
measures a motion. The benchmark wants one manual run before it is trusted.

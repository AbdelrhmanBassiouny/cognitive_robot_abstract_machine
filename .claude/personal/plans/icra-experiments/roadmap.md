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
`failure-predicted-from-the-query` → `experiment-c-in-simulation`, then
`episode-artifacts-recorded` → `cross-episode-question-set-and-ground-truth` →
`experiment-d-in-simulation` (added 2026-09-04; the budget table below does not
yet account for them).

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

## 2026-09-03: the recording is taken from #256 without the demo, and the demo branch takes its detectors

The developer asked what this plan actually needs from montessori-eql-stack's
`montessori_monitor_and_recording` (#256), given that `tracy_icra` works, the
knowledge-directed-perception segmind pull requests work, `tracy_icra_segmind` is waiting to
be merged into `tracy_icra`, and what is really wanted is episodes recorded through ORMatic
with the segmind events in them. Measured rather than argued, and the answer is: about 700 of
#256's 7,124 lines.

### What is needed, and what is not

Needed. The **three lines that make ORMatic able to hold a segmind event at all** - the
`experiments` ORM interface declaring `segmind`, `generate_orm` importing
`segmind.orm.ormatic_interface`, and `experiments/pyproject.toml` declaring the dependency -
and the **recording trio**: `results_database.py`, `results_recording.py` and
`sorting_results.py`. That third one is the episode schema, and it imports exactly two things,
`coraplex.plans.plan.Plan` and `segmind.datastructures.events.DetectionEvent`. Nothing in the
trio touches the simulated world.

Not needed. `world.py`, `semantics.py`, `hole_geometry.py`, `sorting_progress.py` and
`insertion_diagnosis.py` are the Franka simulated demo's, and `tracy_icra` has its own
`world.py`/`semantics.py`/`hole_geometry.py` already (they are close relatives - `world.py`
differs by 46 lines out of 1,180 - but they are two branches' copies, not one file).
`event_monitoring.py` is not needed either, because `tracy_icra_segmind` carries its own,
`experiments/tracy_experiments/montessori/event_monitoring.py`, wired to
`TracyMontessoriWorld` and the Robotiq grasp detectors.

One correction to a premise: #256 has **no cramera import anywhere** - that was the whole
point of splitting it out of #169. It is the demo and the world that do not belong here, not
a viewer dependency.

### Off main, which is what makes it small

`experiments/montessori/` **does not exist on `main` or on #244**. It exists only on #256,
which creates it, and on `tracy_icra`, which has its own. So the extraction cuts off `main`
and creates that directory holding only the three recording modules - no perception
subpackage, no simulated world, and nothing it needs newer than `main` (`Plan`,
`DetectionEvent`, `to_dao` and `create_engine` are all there).

### The defect that was found on the way

#256 had **no `experiments/montessori/__init__.py`**, which #169 carries as an empty file. The
split checked out an explicit file list and missed it. `pkgutil.walk_packages` skips a
directory without one - demonstrated, not assumed - so the ORM generator was never offered
`SortingIterationResult` and `to_dao` would have had no DAO to find: the recording #256 exists
to carry could not have worked. Added in `589aceefd` on that branch, and the extraction takes
it too.

That file is also where the **`Footprint` collision** comes back. It is deferred rather than
avoided: `experiments/montessori/perception/footprint.py` and
`semantic_digital_twin...graph_of_convex_sets/plotting.py` both declare a `Footprint`, so the
moment the `__init__.py` sits over `tracy_icra`'s perception package the generator emits two
`FootprintDAO`s and SQLAlchemy refuses the mapping. `knowledge-directed-perception`'s
`montessori-classes-in-the-orm` (#223) has already renamed the perception one to
`RectifiedFootprint`; whichever branch first puts the two together takes that rename rather
than writing a second one.

### Merging tracy_icra_segmind is a real merge, and small

Not a fast-forward: `tracy_icra` has moved 20-odd commits past their merge base `e034fa791`,
taking the perception work with it. Three conflicts, all identified: `experiments/
requirements.txt` (deleted on `tracy_icra` for `main`'s inline-pyproject convention, which
`test_dependency_declarations.py` tests; `flask` added on `tracy_icra_segmind`, so it moves to
`pyproject.toml`), `segmind/datastructures/events.py` (both sides), and
`tracy_experiments/pickup/pickup_demo_real.py` (both sides).

### The collision this plan should actually worry about

Not #256. **`tracy_icra_segmind` and #244 independently rewrote the same five segmind files**
from `main` - `events.py`, `atomic_event_detectors_nodes.py`, `base.py`,
`spatial_relation_detector_nodes.py`, `episode_segmenter.py` - and a test-merge conflicts in
every one, plus `test_segmind_detectors.py`. **`tracy_icra` and #244 both rewrote the MuJoCo
adapter** as well: `multi_sim.py` is +272/-14 on `tracy_icra` and +650/-36 on #244, and both
add a `panda.py` (add/add). So "is MuJoCo working well" is not a question about #256; it is
this meeting, and it belongs to `integrated-simulation-pipeline` and
`tracy-demo-takes-the-integrated-branch`. It also strengthens the case for splitting #244 by
package, since its segmind third is exactly the colliding part.

### Not taken from #256, and why

`demonstrations.py`'s spin fix is real (a borrowed ROS context raises
`ExternalShutdownException` out of a run that succeeded) but `tracy_icra` uses no
`RobotDemonstrationRosSession`, so it is not this plan's. `Context.simulation_clock`,
`Context.update_world_model_attachment`, `SimulationTimePacer` and the tick budget are all
absent from `tracy_icra`; the attachment gate in particular exists so a simulator holding
objects by contact does not leave the world model believing they are welded, which the MuJoCo
demos may well want - left as the integration item's call rather than pulled in here.

## 2026-09-03: the recording branch, cut and what it had to rewrite on the way

`run-results-recorded-into-sql` is #262, `claude/montessori-results-recording-jnrgfy`,
off `main` with no dependencies. It takes exactly the file list the extraction analysis
above settled on and nothing else, so the branch that lands is the measured ~700 lines
rather than a judgement call made file by file at implementation time.

**Taken, verbatim except for the docstrings:** `experiments/montessori/__init__.py`
(empty), `results_database.py`, `results_recording.py`, `sorting_results.py`, the three
test modules that cover them, the `montessori_results_session` fixture in
`test/experiments_test/conftest.py`, and the four declarations - `experiments` declaring
`("coraplex", "segmind")` in `orm_interfaces.py`, `generate_orm.py` importing
`segmind.orm.ormatic_interface`, and `experiments/pyproject.toml` declaring `segmind`.

**Confirmed before cutting, not assumed:** every import the three modules make resolves
on `main` already - `coraplex.plans.plan.Plan`, `segmind.datastructures.events`,
`krrood.ormatic.data_access_objects.helper.to_dao`, `krrood.ormatic.utils.create_engine`
and `krrood.exceptions.DataclassException` are all there, and
`experiments/src/experiments/montessori/` exists on neither `main` nor #244. So the
branch is additive: it creates the directory and edits four existing files by a line
each.

### The dangling references were wider than the item's notes named

The item asked for the three modules' docstrings to be rewritten because they name
`franka_montessori_demo`, `insertion_experience` and `run_montessori_demo.sh`, none of
which exist on `main`. Reading them through turned up two more of the same kind, both
outside a docstring:

- `DEFAULT_DATABASE_URI`'s docstring cites `coraplex_panda_demo/demo3.py` as the
  precedent for reusing the `semantic_digital_twin` role. That path does not exist on
  `main` either. The reasoning is kept and the citation dropped.
- Both `suggest_correction()` methods tell the reader to provision the database "as
  described in `experiments/src/experiments/montessori/README.md`". That README exists
  on no branch at all - not even #256. These are strings a user reads at a failure, so
  they are repointed at
  `semantic_digital_twin/scripts/create_postgres_database_and_user_if_not_exists.sql`,
  which does exist on `main` and is what `DEFAULT_DATABASE_URI`'s own docstring already
  names as the provisioning step.

The `franka_montessori_sorting_results` database name in `DEFAULT_DATABASE_URI` is
*not* renamed. It is a value rather than a reference, three tests assert it appears in
the failure messages, and renaming it would silently point this branch at a different
database from the demo branch that records to the same one.

### The __init__.py, and why a test rather than a comment proves it

`pkgutil.walk_packages` skips a directory with no `__init__.py`, so without that empty
file the ORM generator is never offered `SortingIterationResult` and `to_dao` has no DAO
to find - the recording could not work at all. That is demonstrated rather than asserted
in prose: `test_montessori_sorting_results.py` imports `ShapeInsertionResultDAO` from the
generated `experiments.orm.ormatic_interface` and round-trips a result through it, so
deleting the `__init__.py` fails a test rather than quietly disabling the feature. This
is the defect #256 carried until `589aceefd`.

### Verification, and what it does not cover

`scripts/regenerate_all_orm.py`, then the three new test modules plus
`test/version_test/test_dependency_declarations.py` - the last being what proves the
`pyproject.toml` line is not merely cosmetic, since `sorting_results.py` is the first
file under `experiments/src` to import `segmind`.

Not covered, and deliberately: nothing here exercises a Postgres database. The tests
reach a Postgres URI only on a port nothing listens on, to prove an unreachable database
falls back rather than fails, so CI needs no credentials and no service.

### The Footprint collision is recorded on the pull request, not fixed on it

The `__init__.py` is what will eventually trigger it: it makes ORMatic walk
`experiments/montessori`, and on `tracy_icra` that directory holds
`perception/footprint.py`, whose `Footprint` collides with
`semantic_digital_twin...graph_of_convex_sets.plotting.Footprint` - two `FootprintDAO`
classes, and SQLAlchemy refuses the mapping. Nothing on `main` triggers it today.
#223 already renames the perception one to `RectifiedFootprint`, so this branch writes
no second rename; #262's description carries the hazard for whichever branch first puts
the two together.

### What the branch could and could not prove in a session container

Green here: `test_dependency_declarations.py` (20 passed, and failing as expected with the
`segmind` line removed, so the declaration is load-bearing),
`test/cognitive_robot_abstract_machine_test/` (61 passed, covering the
`("coraplex", "segmind")` declaration and its generation order), and the `__init__.py`
claim itself - `pkgutil.walk_packages` over `experiments` yields the three montessori
modules with the file present and nothing with it removed.

Not runnable there: `scripts/regenerate_all_orm.py` and the three new test modules, all
for the same reason - no ROS. The generator dies resolving giskardpy's
`DebugExpressionPublisher`, `segmind.datastructures.events` imports `geometry_msgs`, and
the `experiments_test` conftest imports `rclpy`. The regeneration fails identically on
unmodified `main` in that container, which is what settles it as the environment rather
than the change; CI runs both inside the ROS image. Worth knowing for every later item of
this track: anything touching the generated `experiments` interface is CI-verified, not
session-verified.

### The tracy_icra_segmind merge, as it actually resolved

Merged as `a80e86926` and pushed to `tracy_icra` on 2026-09-03. No pull request: a
merge between two of the developer's own branches, done on their explicit instruction.

The three conflicts the plan predicted were the three that occurred, against merge base
`e034fa791` with `tracy_icra` 472 commits past it.

**`experiments/requirements.txt`** stayed deleted, and `flask` moved to
`experiments/pyproject.toml` as planned. What the plan did not anticipate is that the
merge is also the moment `experiments/src` first imports `segmind` at all -- four
modules do, three of them new here -- so `test_imported_workspace_members_are_declared`
demanded `segmind` be declared alongside `flask`. Confirmed by running that test with
the declaration removed: it fails, and passes with it.

**`segmind/datastructures/events.py`** took `tracy_icra_segmind`'s content whole -- the
`Body | Region` `with_object`, `GraspEvent`, `LossOfGraspEvent`, `LiftEvent`,
`StopLiftEvent`, `InsertionEvent.through_hole` as a field rather than a property, and
the switch from `tracked_object.collision.combined_mesh` to `tracked_object.combined_mesh`
so a hole's `Region` root works too -- laid over `tracy_icra`'s rename of `BoundingBox`
to `VolumetricBoundingBox`. That rename is not optional: `BoundingBox` no longer exists
in `semantic_digital_twin.world_description.geometry` on `tracy_icra`, so the incoming
spelling would not have imported. `Region.combined_mesh` does exist there, so the other
half of the change stands as written.

**`pickup_demo_real.py`** kept both sides: `tracy_icra`'s `--record` rosbag arguments and
this branch's event dashboard and slip watch, with argument parsing ahead of the dashboard
so a bad flag exits before a web server starts.

#### The one judgement call, recorded because it is a hardware number

`SHAPE_TABLE_CLEARANCE` and `GRASP_HEIGHT_OFFSET` looked like a value conflict and were
not. `tracy_icra_segmind` deleted `SHAPE_TABLE_CLEARANCE` outright: it stopped spawning
shapes hovering above the table (so SegMind's own support and contact detectors see them
resting on it) and raised the *grasp target* by `GRASP_HEIGHT_OFFSET` instead, which is
the same physical distance under a different decomposition. Both of the old constant's
readers are gone, so keeping it would have left a dead name and lost the offset.

`tracy_icra` had meanwhile tuned that distance from 0.032 to 0.04 on hardware, in
`e8aef78f6` ("Added recording for rosbags"), alongside the same move for `PLACE_HOVER`.
The merge carries the 0.04 onto `GRASP_HEIGHT_OFFSET`. Taking the incoming 0.032 would
have silently reverted a hardware tuning; taking the old name would have broken the new
design. **If 0.04 was tuned against the old spawn-hovering geometry specifically rather
than against where the arm has to reach, this is the line to revisit** -- it is the only
number in the merge that came from a run rather than from either branch's text.

#### The silent-conflict sweep, and what it found

Six passes over the merged tree, none of which an import resolver or pyflakes would have
made:

1. **Module-level name inventory** on both sides against the merge base. `tracy_icra`
   removed twelve names in the four source packages; every one turned out to have moved
   modules rather than vanished, and every reader still resolves. `tracy_icra_segmind`
   removed exactly one, `SHAPE_TABLE_CLEARANCE`, handled above.
2. **Import resolution** over the whole tree without executing anything, diffed against
   both parents. The merge introduces no unresolved import.
3. **Identifier-shaped string literals** in every merged-in file, checked against what the
   tree defines. All resolve -- including `_KNUCKLE_JOINT_TEMPLATE`'s
   `"{side}_robotiq_85_left_knuckle_joint"` and `"/{side}_gripper/joint_states"`, which
   are the names `TracyJoint` and Giskard's Tracy config still use.
4. **Attribute reads** in every merged-in file. Everything unmatched is stdlib or
   third-party; nothing from the workspace is dangling. `end_effector.thumb.tip` and
   `.finger.tip` resolve through the `HasTwoFingers` mixin that `TracyLeftGripper` carries.
5. **Keyword arguments** against the signatures the merged tree declares, diffed against
   the same sweep run on `tracy_icra_segmind` itself. The merge introduces none.
6. **Enum members** named by merged-in files, against 204 enums. All resolve.

The near miss worth naming: `grasp_detector_nodes.py` calls
`contact(object, finger_tip)` and expects a bool, while `tracy_icra` rewrote
`reasoning/predicates.py` (+567/-195) and turned `contact` from a plain function into
`symbolic_callable_to_function(InContactWith)`. That is safe -- the wrapper returns the
computed value when no argument is a variable, which is what it exists for -- but only
because the migration was built to preserve the name's call behaviour. The base version's
`threshold` parameter is now `maximum_distance`; the single call site passes neither.

#### Tests were not run here, and why

`test/segmind_test` and `test/experiments_test` cannot run in a Claude Code web session:
`segmind.datastructures.events` imports `geometry_msgs.msg` at module scope, and `rclpy`
has no PyPI distribution at all. CI runs both inside a ROS container
(`ghcr.io/<repo>:jazzy`, with `/opt/ros/cram-env`), which is where they have to be run.
The local `uv` is also older than CI's and cannot parse the root `pyproject.toml`'s
`override-dependencies` map form.

What was verified locally instead: every file the merge touches parses, the six sweeps
above, and `test_dependency_declarations.py` executed directly against all ten workspace
members -- twenty checks, all passing, which is the test that governs the
`requirements.txt` resolution.

`ci.yml` triggers on push to `main` and on pull requests, so this push to `tracy_icra`
runs nothing. **The suites still need a run** -- on the next pull request that carries
this branch, or by hand in the container.

## 2026-09-04: the integrated branch, its merge order and the four meetings it resolves

`integrated-simulation-pipeline` is #265, `claude/icra-experiments-simulation-pipeline-w4ep7n`,
cut off `main` with no dependencies. The merge order is the item's own, with one branch added
and one done-criterion changed; both are recorded below rather than left to the diff.

The order, and what each merge actually cost, measured by a dry run over the real branches
before anything was committed:

| step | branch | conflicts |
|---|---|---|
| 1 | #244 `sdt_segmind_krrood_from_fast_monitor` | none |
| 2 | #256 `montessori_monitor_and_recording` | none |
| 3 | #262 `claude/montessori-results-recording-jnrgfy` | 3 add/add: the recording trio |
| 4 | #229 `sdt_predicates_answer_whether_they_hold` | `reasoning/predicates.py` and its test |
| 5 | #238 `claude/kdp-search-constraints-pfaph7` | `world.py`, `semantics.py`, `hole_geometry.py` and their three tests |
| 6 | #236 `claude/plan-item-kickoff-ge8541` | `perception/pipeline.py`, `perception/recorded_setup.py` |
| 7 | #231 `claude/choose-detection-method-gf64yp` | four perception modules, `geometry.py`, one test |
| 8 | #223 `claude/montessori-classes-orm-s7vxu1` | the `RectifiedFootprint` rename over the perception tips |
| 9 | #239 `3a493be9` only | cherry-pick, the measured colours and finishes |

### The three meetings the item predicted, and the fourth it did not

Predicted and confirmed: **#262 against #256** on the recording trio, resolved by taking
#262's copies, which are the same modules with the dangling references repointed;
**#244 against #229** on `reasoning/predicates.py` (+184 against a 759-line rewrite) and
`geometry.py`; and **#231's `EdgeFitDetector` rename**, which arrives with step 7.

Not predicted, and the one that would have stopped the branch: **the perception stack and
#256 each build their own `experiments/src/experiments/montessori/`**. The directory exists
on neither `main` nor #244 — #202 creates it with 43 files, #256 with 10, and their
`world.py`, `semantics.py` and `hole_geometry.py` are close relatives rather than one file
(1,180 against 1,149 lines; 479 against 318; 236 against 293). The item's notes named this
collision as `tracy_icra` against #169; on this branch it is the perception lineage against
#256, and it meets in full.

The perception lineage's copies survive. They are the larger, reviewed lineage that is
landing on `main` through #202, and the extraction analysis of 2026-09-03 had already judged
#256's copies to be "the Franka simulated demo's". What the monitor needs from them is
narrow — `event_monitoring.py` imports exactly `MontessoriShape` from `semantics` and
`MontessoriWorld` from `world`, both of which the perception copy defines — so the merge
order puts #256 before #238 and takes #238's side, and only what the monitor needs and the
perception copy lacks is carried forward.

### #223 joins the merge list, because this is the branch that puts the two Footprints together

`roadmap.md` already assigned the `Footprint` rename to "whichever branch first puts the two
together". That is this branch, and the trigger is exactly the one predicted: #262's
`experiments/montessori/__init__.py` makes `pkgutil.walk_packages` descend into the
directory, where the perception stack's `perception/footprint.py` declares a `Footprint`
that collides with `semantic_digital_twin...graph_of_convex_sets.plotting.Footprint`. Two
`FootprintDAO` classes and SQLAlchemy refuses the mapping.

#223 already renamed the perception one to `RectifiedFootprint`, so the branch merges #223
rather than writing a second rename. It goes in after the perception tips, not before, so
the rename lands over them instead of being conflicted against by each in turn.

### The done-criterion moved, because neither demo entry point lands here

The item's notes ask for `franka_montessori_demo` and the Tracy simulated demo to sort the
board headless. Checked rather than assumed: `franka_montessori_demo.py` exists only on
#169, which is deliberately excluded, and `montessori_demo.py` only on `tracy_icra`, which
this branch does not merge — `tracy-demo-takes-the-integrated-branch` merges in the other
direction, and later. So as the merge list stands the criterion is not checkable on this
branch at all.

Settled with the developer on 2026-09-04: **this branch writes its own headless integration
test** over the merged world, event monitor and predicates, and the demo proof belongs to
`tracy-demo-takes-the-integrated-branch`. Porting a copy of `montessori_demo.py` here was
the alternative, and it was rejected because a copy carrying no shared history buys a
checkable criterion now at the price of an add/add conflict when the two branches meet.

### What this branch cannot verify, and who does

`scripts/regenerate_all_orm.py`, `test/experiments_test` and `test/segmind_test` do not run
in a Claude Code session container: the generator dies resolving giskardpy's
`DebugExpressionPublisher`, `segmind.datastructures.events` imports `geometry_msgs` at
module scope, and `rclpy` has no PyPI distribution. This is the same limit #262 recorded,
and it applies to every item of this track. CI runs both inside the ROS image, so the merge
resolutions and the ORM regeneration are CI-verified rather than session-verified.

## 2026-09-04: what the merge actually cost, and the two branches it could not take

Six of the nine steps landed on #265. The three predicted meetings resolved as planned;
a fourth appeared that the notes had named in the wrong pairing; and two branches turned
out not to be mergeable as text at all.

### predicates.py is rewritten by three branches, not two

The item's notes predicted #244 against #229. The perception lineage rewrites the same
file too, +1107/-257, and its version is a superset of #229's by name - the two carry the
same class design, including the verbalization fragments, though their merge base is
`main` and neither is an ancestor of the other.

So #238's copy takes the structure and #244's numeric readings are re-applied over it.
#238 had meanwhile redesigned the view-relation machinery entirely - `axis` as a
`ClassVar[SpatialVariables]` plus a `positive_side` flag, in place of #244's `ViewAxis`
enum and `signed_distance_along_axis` - so the fast path is re-expressed rather than
restored: `unit_axis_of` is the one home for the direction maths, and both `_direction`
and `SupportedBy` read through it. `Below(...)()` and #244's numeric reading were checked
to be the same comparison before one replaced the other.

This matters because #244's four tests assert the path builds nothing symbolic, and they
are in the tree. Dropping the fast path would have failed them, and AGENTS.md forbids
adjusting a test to fit.

### the montessori package meets in full, and it costs one module

Predicted, but as `tracy_icra` against #169. On this branch it is the perception lineage
against #256. The perception copies survive, for the reasons the extraction analysis of
2026-09-03 already gave.

The cost is `sorting_progress.py`. It reads `shape_key`, `object_name`,
`insertion_target_for` and `has_fallen_through`, all four of which belong to #256's
semantics copy and have no counterpart in the surviving one, whose vocabulary is
`hole_for`, `fits_through` and `cross_section_size`. Nothing imports it but its own test,
and the same analysis had already called it the Franka demo's, so it was removed rather
than kept alive by porting four members of the losing copy onto the winning one.

### the Footprint rename was taken without its branch

The hazard fired exactly as predicted, and it is blocking rather than cosmetic: without
the rename the ORM regeneration this item owes cannot run at all. #223's identifier was
applied directly, character for character, so the two do not fight when #223 lands.

### #231 and #223 both fork before #236 rewrote BoardDetector

This is the finding that stopped the merge, and it is one finding covering both branches.
Neither is a text merge onto this branch: each has to be re-applied onto a detector that
has since been rewritten.

#231 is the harder half, and it is a design synthesis rather than a conflict resolution.
It renames `LoosePieceDetector` to `EdgeFitDetector`, makes it a `PieceDetector` declaring
a `capability(look)`, adds `ColorBlobDetector` beside it, and restructures the pipeline's
`look()` around `detector_rules.detectors_for(...)`. The perception tip meanwhile grew the
same class expectation-driven and colour-narrowed search with `Occupancy` de-duplication.
A merged pipeline has to do both. That is ~200 conflicted lines over 10 hunks through the
core perception loop, and nothing on this branch can be executed to check the result.

Left for a deliberate pass rather than resolved under the deadline. The #239 cherry-pick
waits on it, since `3a493be9` sits on top of #231.

### nothing on this branch has been run, and that is now measured rather than assumed

The workspace does not install in a session container: `random_events` needs a C++ library
that will not build there, and the ROS imports #262 already recorded stand. Verification
was static - whole-tree parse, no leftover markers, every workspace import in the merged
and edited files resolved against what its module defines, and the four missing members
confirmed absent before `sorting_progress.py` was removed.

One process note worth keeping: `format_docstrings.py` over "modified files" reformats
everything a merge dragged in, which on an integration branch is most of the tree and
would conflict with every owning branch. It was restricted to the files this branch
actually edited.

### 2026-09-04: a fourth experiment, because long-term memory was built but never scored

The developer noticed that the plan tracks no long-term-memory *experiment* and asked
where those items were. They were half there. `episodes-recorded-through-ormatic` and
`episodes-queried-by-eql` build the machinery, `segmind-detectors-on-the-demo-branch` is
`done` (and so hidden by the dashboard's default "hide done items" toggle, which is why it
looked absent), and the segmind events are in the episode model's own notes. What was
missing was anything that *measures* it: Experiments A, B and C all ask about the current
scene, `experiment-a-in-simulation` depends on `episodes-recorded-through-ormatic` but not
on `episodes-queried-by-eql`, so the long-term-memory spelling of the temporal bucket that
`question-set-and-ground-truth` explicitly calls for had no consumer. The plan's own
description calls long-term memory a deliverable, and it was producing no number.

#### What Experiment D asks

The same four buckets, asked of the history rather than the scene: has this happened to
the robot before and in which episode; what the goal and the conditions were at that time;
what differed between the earlier episodes and the current one that bears on the question;
and how a failure was resolved the last time it happened. That last one is why
`episodes-recorded-through-ormatic` grew a line: it recorded the failure type observed and
predicted, but not what was *done* after the failure, and nothing else in the record
carries the resolution.

#### The three decisions taken, and why

**Its own experiment, not a fourth bucket of A.** A and D put different systems under
test — one VLM looking at an image of the current scene, one VLM reading a corpus of past
episodes — with different ground truth and a different fairness argument. Folding them
makes A's per-bucket accuracy table mix two incomparable systems.

**Simulation only.** The questions are about recorded episodes, so they do not care
whether an episode came from the robot or the simulator; the robot episodes A and C record
join the same corpus. This buys a whole experiment for no robot time. The condition is
that simulated episodes must record video and simulation data, which is
`episode-artifacts-recorded`.

**The VLM gets the whole corpus, capped so it fits — not a retrieval step.** Retrieval was
considered first and rejected: it scales to any corpus, but a wrong answer is then
ambiguous between "retrieval never surfaced the episode" and "the model had it and
reasoned wrong", which is exactly the distinction the experiment exists to make. Capping
the number of episodes a question may reach over, derived from what the model's context
holds once the video frames are sampled, means the model is provably given everything the
SQL backend can see over the same episodes — so a loss is a reasoning failure. The cap
becomes the baseline's stated limitation in the paper.

That decision also simplifies the availability metric the developer asked for. With one
shared corpus rather than a per-system retrieval, *whether the information needed to answer
is present at all* is a property of the corpus, measured once, not a per-system score. A
question nothing could have answered is then scored apart from one both systems had the
evidence for.

#### Why `episode-artifacts-recorded` is separate rather than folded

The scope check (`check_scope_overlap.py --base origin/main`) found no in-flight branch
sharing this work's paths: #265, #262, #256 and `tracy_icra` share none, and #261 shares
only `experiment_definitions.py`. `experiments/src/experiments/scenarios` and
`experiments/src/experiments/montessori` are absent from `main` because #261 and #262
create them — unlanded parents this sits on, not owners of it.

The one real fold candidate was `episodes-recorded-through-ormatic`, which is
`not_started` with no branch. It stayed separate because the artifacts need
`simulated-camera-feeds-perception` (lane 1) for the camera frames, and folding would put
lane 2's foot item — which four other items wait on — behind lane 1's second item.

Duplicate-intent scan: `montessori_event_replay` (#165) records `DemoRecording` /
`RecordedFrame`, but those are world-state snapshots in a rolling in-memory buffer for the
console's replay viewer, inside `cramera`, which this plan excludes. Not a per-episode
video on disk, so not a duplicate.

#### Left to the developer

The budget table above allocates twelve days across three experiments. A fourth is not in
it, and re-budgeting an 11-day deadline is the developer's call, not something to invent
here. One suggestion to accept or reject: if time runs short, cut D's VLM arm first and
keep the EQL-over-SQL numbers, which need no external model or credentials — the same
shape the memo's cut order already takes with B's injection half.

The open question about which vision-language model and provider the baseline calls now
covers D as well, and gains a second part: how many episodes fit one context once video
frames are sampled, which is what sets D's cap.

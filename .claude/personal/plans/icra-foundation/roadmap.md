# icra-foundation: roadmap

One of three successors of `icra-experiments`, split 2026-09-05 for the plan
size budget (`plan-size-limits`, tracking issue #200) — the item limit alone
(33 > 15), not the line budget. The split is by wave, the plan's own
existing organizational seam: `icra-foundation` is the `foundation` wave,
`icra-mechanism` is `mechanism`, `icra-evidence` is `evidence`. All three
keep `tracking_issue: 252`, the original mailbox. Full split rationale and
what it cost lives in `plan-size-limits/roadmap.md`'s "Done 2026-09-05:
`split-icra-experiments`" section; the predecessor's full roadmap is
reachable in the personal-notes branch's history immediately before the
split commit.

This roadmap keeps what binds future work: the plan's why, the standing
design decisions, the hazards and open questions, and — since every item
here already has an open pull request or is `done` — what each branch
actually merged and what it cost, compressed to what a later branch touching
the same files needs to know. Per-round conflict-resolution narrative (which
hunk, which commit) is compressed to its outcome; the pull requests
themselves are that record and are linked.

## Why this plan exists

**Restated 2026-09-08** (the original thesis sentence is kept below it, since
every item's notes were written against it). The paper's claim is that one
knowledge representation and one query language serve every subsystem of a
cognitive robot architecture at once: the perception system writes into it —
whatever the perception system is, a classical detector stack, a
vision-language model or a visual-question-answering model — the control
program reads it as the constraints of its optimization and reports back
into it, the event-segmentation system moves it as things happen, working
memory is its current state and long-term memory is its recorded history.
Because it is one representation, one query language asks questions of all
of them; and because the questions are answered from a database rather than
from a model, they are answered at a fraction of the cost. `krrood` is
KnowRob 3.0, and this is the paper that shows what the third iteration buys.

The original sentence, which the mechanism items are still written against:
the same EQL query answers a question, selects which backend answers each
predicate, drives what the robot perceives, and verifies the result in the
digital twin; removing knowledge produces failures the query predicts.

Nothing before this plan owned the experiments, the scenario definitions,
the episode recording, the capability routing, the physics verification, the
failure taxonomy, the VLM baselines or the artifact — see the predecessor's
history for the full survey of what `knowledge-directed-perception` already
owned instead.

**This wave is the foot of the whole programme.** `integrated-simulation-pipeline`,
`scenario-domain-model` and `run-results-recorded-into-sql` can all start in
parallel with no dependencies, and every mechanism/experiment item in
`icra-mechanism`/`icra-evidence` stacks on one of the twelve items here.

## What the code already had, and what this wave builds on

- **Narrowing is measured** (#238, 0.25–0.43 of an unnarrowed look on six real
  captures) and **decomposition exists implicitly** (#238's lid/hole answered
  from the twin before a look; #231 gives each detector a `capability`) —
  `icra-mechanism`'s `backend-routing` track raises both one level.
- **The verification predicates exist** (#229: support, contact, visibility,
  reachability, stability, occupancy, inside-of, six directional relations),
  consumed by `icra-mechanism`'s `physics-verification-backend`.
- **Episode recording existed in three shapes** — `ShapeInsertionExperience`,
  `SortingIterationResult`, and the console stack's `SegmindEventRecord`/
  `InsertionAttemptRecord` — all through ORMatic already.
  `episodes-recorded-through-ormatic` replaces the first two with one
  `Episode` model.
- **A scenario abstraction and a result model exist**:
  `control_loop_experiments.scenarios` (`BenchmarkScenario`,
  `ScenarioRunner`) and `experiment_definitions` (`ExperimentResult`,
  `ExperimentsTable`, `TypstRenderer`). `scenario-domain-model` generalises
  both.
- **Failure diagnosis exists** (`insertion_diagnosis.InsertionDiagnosis`,
  `InsertionFailureReason`), extended by `icra-mechanism`'s
  `failure-taxonomy-and-typing`.
- Segmind emits temporal/embodiment events via **EQL rules, not ripple-down
  rules** (developer correction, 2026-09-03); the twin answers gripper
  contents through `bodies_in_gripper`; #169 already restored attach-on-grasp
  behind `Context.update_world_model_attachment`, which
  `snapshot-working-memory` (in `icra-mechanism`) relies on.
- Verbalisation is deterministic by construction; the scene wordings are on
  #33 (owes a rebase onto #229, two wording decisions open — developer's
  call), reused by `icra-mechanism`'s `working-memory-verbalised`.

## Structural decisions taken at creation (2026-09-03)

- The two core mechanisms (per-predicate routing, physics verification) live
  in `icra-mechanism`, not `knowledge-directed-perception`; that plan's
  `imagination-world-rejects-what-a-predicate-refuses` item is covered by
  `physics-verification-backend` in narrow form.
- `integrated-simulation-pipeline` is the whole programme's foot item.
  `tracy_icra` stays the real-robot integration point;
  `knowledge-directed-perception`'s three demo items are satisfied by
  `tracy-demo-takes-the-integrated-branch` (here) and the robot experiments
  in `icra-evidence`.
- SQL is a backend and long-term memory is a deliverable (developer
  correction, 2026-09-03): EQL over an SQL database returning domain objects
  is the long-term-memory feature; every scenario's episodes, real and
  simulated, are recorded into it through ORMatic and are to be queried —
  this wave's `long-term-memory` track.
- Simulation first: every scenario, demo and perturbation runs through the
  full integrated pipeline in simulation before the robot, which is why
  every experiment in `icra-evidence` has an in-simulation item its robot
  item depends on.
- Scenarios are data: a dataclass domain model (`scenario-domain-model`)
  describes scenarios/goals/conditions/perturbations/metrics at a meta
  level; concrete scenarios subclass or instantiate it.
- #192 is the developer's own and stays out of the integration branch until
  he says it is in (it removes `Match.variable`, which #159 and so #239
  still read).

## Cross-plan prerequisites relevant to this wave

Decided 2026-09-03: work another plan already owns stays there; the item
here that needs it carries a blocker naming it.

- **knowledge-directed-perception.** Everything built in its `surfaces`,
  `request-language` and `method-selection` tracks (#202, #205, #216, #221,
  #222, #225, #227, #229, #231, #232, #236, #238, #239's knowledge-half
  commit) is consumed by `integrated-simulation-pipeline`; this wave does not
  wait for those pull requests to land. Its three demo items are satisfied
  by `tracy-demo-takes-the-integrated-branch` and the robot experiments in
  `icra-evidence`.
- **montessori-eql-stack.** #244 and #256 are merged into the integrated
  pipeline; #169 is not (#256 was split out of it so this programme need not
  take the cramera console). What is left of #169's debt here is the
  unbounded `SimulationTimePacer.sleep()` (see Standing hazards below), and
  that plan owns it. The console stack above #169 is not needed for any
  number in the paper.
- **eql-verbalization.** #33's reviewed scene wordings are what
  `working-memory-verbalised` (in `icra-mechanism`) renders with; that item
  does not wait for #33 to land.
- **Not on the deadline path:** eql-performatives, eql-existential-semantics,
  match-query-ergonomics (#192 is the developer's own), the rdr-* plans, and
  every tooling plan.

## The budget: 2026-09-15

Twelve days from 2026-09-03, across all three successor plans' work (the
original three-lane budget table is unchanged by the split — see
`icra-mechanism`/`icra-evidence` roadmaps for the lane assignments that use
it). This wave's state-reached milestones: **Thu 3/Fri 4 — the simulated
demo runs the whole pipeline and records episodes**; **Sat 5/Sun 6 —
go/no-go Sunday evening: routing and physics verification (in
`icra-mechanism`) answer a mixed query in simulation**, which needs this
wave's pipeline and episode recording in place first.

If the go/no-go fails, the memo's fallback holds: submit with Experiments A
and C and drop B's injection half, keeping the decomposition numbers from
#238. **Cut order:** lighting → the optional no-narrowing ablation → a
second setup → fewer random scenes → B's injection half. **Never cut:** the
temporal scenarios, the perturbation conditions, the hybrid VLM baseline,
the failure-prediction metric, the determinism runs.

## Memo corrections this wave carries

- There is no in-hand event and no Flanagan model. In-hand is a twin
  predicate; the pick-up detector is an EQL-rule detector over contact and
  support.
- The board mesh is 0.865 times the real board (#236). Ground truth from the
  twin and the no-hole-shape-knowledge condition (`icra-mechanism`) both
  need the scale in the twin first.
- Only one of the six recordings carries robot state. Every future take
  records the transform tree and joint states with the camera —
  `tracy-demo-takes-the-integrated-branch`'s standing instruction.
- The continuous perception node cannot hold the frame budget once the hole
  layout fit runs (0.56 s against 0.5 s); `snapshot-working-memory` (in
  `icra-mechanism`) is what makes that irrelevant.

## Standing hazards

- **`SimulationTimePacer.sleep()` is unbounded.** A stalled simulation blocks
  a tick forever; no test reaches it, only the demo scripts set
  `context.simulation_clock`. What a stalled simulation should do is the
  developer's call, not decided here. Inherited by
  `integrated-simulation-pipeline` from the #169/montessori-eql-stack
  lineage.
- **The `Footprint` collision.** `experiments/montessori/perception/footprint.py`
  and `semantic_digital_twin...graph_of_convex_sets.plotting.py` both declare
  a `Footprint`; the moment ORMatic walks a package holding both,
  it emits two `FootprintDAO` classes and SQLAlchemy refuses the mapping.
  `knowledge-directed-perception`'s `montessori-classes-in-the-orm` (#223)
  renamed the perception one to `RectifiedFootprint`; `integrated-simulation-pipeline`
  merges #223 rather than writing a second rename, and did so after the
  perception tips so the rename lands over them. It is not a one-off: the same
  shape recurred as two `RecordedLook`s within `experiments.montessori` itself
  (cleared by #292, above), so the hazard is any bare class name reused anywhere the
  generator's package walk reaches -- upstream or in the same package.
  `test_montessori_orm.py` now asserts both directions for that package.
- **#231 and #223 both fork before #236 rewrote `BoardDetector`.** Neither is
  a text merge onto `integrated-simulation-pipeline` — each has to be
  re-applied onto a detector rewritten since. #231 in particular is a design
  synthesis (`EdgeFitDetector`, `ColorBlobDetector`, `detector_rules.detectors_for`)
  against the perception tip's own expectation-driven, colour-narrowed
  search — ~200 conflicted lines over 10 hunks, left for a deliberate pass
  rather than resolved under the deadline. The #239 cherry-pick (`3a493be9`)
  waits on it.
- **Two databases, one host, until a rename catches up.** `run-results-recorded-into-sql`
  renamed its database from `franka_montessori_sorting_results` to
  `montessori_sorting_results` in review (2026-09-05, developer override);
  until #256 takes the same rename, its Franka demo and the Tracy demo
  record to different databases on the same host.
- **A domain class named like a typing alias breaks ORM generation.** Fixed in krrood
  (see the generator's name collision below), but the shape recurs: a class diagram
  resolves annotations with the classes it holds, so a class whose name a module also
  imports from `typing_extensions` is worth noticing before the generator meets it.
- **An annotation the ORM generator has never met writes code nobody reads.** Its first
  reader is the interpreter importing the generated interface, so a field shape new to
  the workspace -- `SurfacePass` was the first to declare `Sequence[...]` -- surfaces as
  a `NameError` or a mapping error in CI rather than as anything a session can see. And a
  generated module that fails halfway leaves its already-registered tables behind, so the
  cascade reads as many unrelated failures.
- **Nothing on these branches runs in a session container.** `random_events`
  needs a C++ library that will not build there, and
  `scripts/regenerate_all_orm.py`/`test/experiments_test`/`test/segmind_test`
  need ROS (`geometry_msgs`, `rclpy`, giskardpy's `DebugExpressionPublisher`).
  CI runs both inside the ROS image (`ghcr.io/<repo>:jazzy`), so every item
  touching the generated ORM interface or segmind is CI-verified, not
  session-verified — true for every item in every successor plan that
  touches those modules.

## Open questions for the developer

- Whether `knowledge-directed-perception`'s `expectations-from-events` is
  still needed once `snapshot-working-memory` and `failure-taxonomy-and-typing`
  (both `icra-mechanism`) exist, or whether the violated-expectation report
  folds into failure typing there.

## What each branch merged, and what it cost

### `integrated-simulation-pipeline` (#265) and `segmind-detectors-on-the-demo-branch`

The foot item's merge order is nine branches deep: #244, #256, #262
(3 add/add conflicts on the recording trio), #229 (`reasoning/predicates.py`),
#238 (`world.py`/`semantics.py`/`hole_geometry.py`), #236
(`perception/pipeline.py`, `perception/recorded_setup.py`), #231 (four
perception modules, `geometry.py`), #223 (the `RectifiedFootprint` rename),
and #239's one measured-colours commit (`3a493be9`) cherry-picked.

Two meetings the item's notes did not predict, both settled: the perception
lineage and #256 each build their own `experiments/src/experiments/montessori/`
(#202's 43 files vs #256's 10) — the perception copies survive, and the cost
is one module, `sorting_progress.py`, which reads four members only #256's
losing copy defined and was removed rather than kept alive. And
`reasoning/predicates.py` is rewritten by three branches, not two (#244,
#229, and the perception lineage's own +1107/-257) — #238's copy took the
structure, #244's numeric readings were re-applied over it, and #244's fast-path
tests (which assert no symbolic construction) still pass.

The done-criterion moved: neither demo entry point (`franka_montessori_demo`
on #169, `montessori_demo.py` on `tracy_icra`) lands on this branch, so it
writes its own headless integration test over the merged world, event
monitor and predicates; the demo proof belongs to
`tracy-demo-takes-the-integrated-branch`.

`segmind-detectors-on-the-demo-branch` (`done`) merged `tracy_icra_segmind`
into `tracy_icra` as `a80e86926` (a real merge, not a fast-forward — 472
commits apart at merge base `e034fa791`): three conflicts, all predicted and
resolved (`requirements.txt` stayed deleted, `flask` moved to
`pyproject.toml`; `segmind/datastructures/events.py` took the incoming
content over `tracy_icra`'s `BoundingBox`→`VolumetricBoundingBox` rename;
`pickup_demo_real.py` kept both sides). One hardware-tuned constant
(`GRASP_HEIGHT_OFFSET`, 0.04) was kept over the incoming 0.032 — flagged as
the one number in the merge that came from a run rather than either
branch's text, worth revisiting if 0.04 was tuned against the old
spawn-hovering geometry specifically.

#### The convergence pass, 2026-09-06

Every in-flight branch of the two knowledge-directed plans, the ripple-down rules
stack and match-query-ergonomics was merged onto #265 in one pass, so the ICRA
experiments run on one tree. Seven merges, each at its own tip and each into #265 —
never sideways into each other, which would have paid the same conflict set twice:

1. **#223** `montessori-classes-in-the-orm`. Its substance was already here
   (`montessori/__init__.py`, the `RectifiedFootprint` rename); what it adds is
   `test_montessori_orm.py`. Both conflicts resolved to this branch's newer
   detector code.
2. **#270** `competing-explanations`, carrying #225, #232 and #236. `detect()` keeps
   the colour it is narrowed by and gains the board outlines and the comparison
   thresholds.
3. **#257** `expectations-from-events`, carrying #227, #238, #255 and #246.
   `reasoning/predicates.py` took #257's already-settled resolution.
4. **#229** `predicates-answer-whether-they-hold`. A pure ancestry merge: it changed
   no file, because this branch already carried the predicate classes at an older
   tip and #229's only newer commits are merges of `main`.
5. **#275** `a-look-is-described-by-a-match`, carrying #231, #239, #266 and #259.
6. **`D-deco` (#77)**, the whole ripple-down rules stack. A clean text merge.
7. **#192, #196, #248**, the whole match-query-ergonomics set (#254 arriving with
   #192).

Both standing exclusions this item's notes carried are reversed at the developer's
direction: the whole RDR stack is in rather than #239's one knowledge-half commit,
and #192 is in.

**What the merge cost, and what it removed.** #275 and the #227/#236/#238/#257
lineage are two rewrites of the same pipeline, so most of the work was putting each
capability where the other design says it belongs. The look's own knowledge —
the request narrowing, the expectations, the imagined world, the table the board
hides — moved onto `SceneToSearch`, and `FindThePieces` reads it there instead of
the pipeline doing it inline. A detector is handed one `SurfacePass` rather than
nine positional arguments, which is what let the two designs' parameter lists meet.

Duplication the text merge would have left standing, all of it removed here:
`SUPPORTING_SURFACE_ATTRIBUTE_NAME` (superseded by #227's `narrowing_relations`);
`VIEW_DIRECTION_EPS` defined twice in `predicates.py`, and
`_supported_stands_below_supporting` re-deriving what `unit_axis_of` computes;
`_outlines_wearing` identical on both piece detectors, now `SurfaceColors`'s;
`piece_height = 0.03` on each detector, now `LOOSE_PIECE_HEIGHT` on `PieceDetector`;
`workspace_over` with two definitions under one name, the second silently shadowing
the first; and `CanBehaveLikeAVariable` declared twice in `mapped_variable.py` after
#248 — a conflict resolved wrong on the first pass and amended.

**The collision git could not flag, twice.** The known one was #192 removing
`Match.variable`, which #159 and therefore #239, #266 and #275 read. Because #192
also gives `Match` symbolic attribute delegation, a stale read does not raise — it
builds an `Attribute` expression for a field called "variable". They were found by
making `Match._is_own_name_` refuse the retired spellings temporarily, running the
suites, and migrating every hit; the guard was then removed, since #192 deliberately
leaves every public name to the matched class.

The second was not predicted, and the first answer to it was wrong. #257 fixed the
grid a sweep walks — laid out from the centre outwards, so widening a belief's reach
only *adds* placements — while the #225/#232/#236 lineage extracted the whole sweep
into `OutlineFitter`, carrying its own edge-anchored grid with it. Merged textually,
`offsets_within` would have arrived unused beside the phase bug it was written to fix,
with #257's four tests still passing against code no longer reached. So the pass
unified them on the centred grid — **and the captures said no.** A believed reach is a
bound, so its grid is centred on the claim and stops inside it; the board's seed search
is pointed at the middle of whatever the lighting made dark and has to reach the whole
radius it was given. Walking the centred grid for that seed shortened its forty
millimetre search to thirty-six and left three of the board's six holes over wood on
`tracy_pickup_demo`. The two grids are two, named for what each means: `offsets_within`
and `OutlineFitter.placements_within` for a belief, the fitter's own lattice for a
search. This is the general lesson of the pass — two things that look like one
operation are not one when their contracts differ, and the ground truth is what says
which.

**What was measured.** The six real captures, run through the pipeline before and
after with the same script: #265's tip missed 7 pieces and invented 3; the converged
tree misses 6 and invents 1, and finds the board on all six. No capture got worse.

**Left for the developer.** After the merge, `EdgeFitDetector` and
`ColorBlobDetector` differ only in how tightly a blob's place is believed before
the outline is fitted — a radius and a turn — which is a parameter rather than a
subclass. Collapsing them into one detector the rules configure two ways is a design
call, not a merge resolution, so it was not taken here.

#### The generator's name collision, 2026-09-06

CI had never been green on #265, and the whole of it was one root cause: ten of the
twenty-three checks -- every job that builds the workspace ORM interfaces -- died in
generation with `CouldNotResolveType` on `SurfacePass`, "type 'Sequence' is not
subscriptable", before a single test ran. `main` was green at the same base, so none of
it was inherited. The jobs that passed are the ones whose conftest never builds an
interface, which is why the failure read as scattered rather than as one thing.

Resolving a field, `ClassDiagram` offers every class it holds by bare name -- the
workaround that lets an annotation reach a type its module imports only for type
checking. It offered them as a *local* scope, and a local scope beats the module the
annotation was written in, so giskardpy's `Sequence` goal (the generator walks
giskardpy) replaced the typing alias `detector_choice.py` had imported. The fix is in
`krrood.class_diagrams.utils.get_type_hints_of_object`: those classes now fill only the
gaps the defining modules leave.

The convergence's own `SurfacePass` was simply the first mapped class in the workspace
to annotate a field `Sequence[...]`, and three more classes already answer to a typing
name -- `Union` in the entity query language, `Type` in robokudo, `Set` in
`random_events` -- so this was one annotation away from happening again, in any plan.

What it cost is that nothing the convergence merged has been exercised by CI at all:
the generation aborts before collection. The measurements the convergence recorded
stand -- they were taken by a script, not by the suites -- but every suite number in
#265's description was taken in a session container with the ORM-dependent modules
excluded, which is the container hazard above. A branch whose one untested path is the
one only CI can run needs CI to have run before it is called verified.

#### What the wall was hiding, 2026-09-06

CI collected for the first time on `f5c383a8`: thirteen of the fifteen jobs green,
`Examples and Demos` green in full, and each of the two that failed one defect of this
branch's own.

The experiments interface would not import at all, and the fifteen failures and errors
of that job were one cause, not two. A relationship is rendered with the container its
field declares, and `SurfacePass` declares the abstract `Sequence`, so the generated
module named `collections.abc.Sequence` without importing it -- but naming it would not
have helped, since SQLAlchemy instruments a collection in place and needs one it can
build empty and append to, which `Sequence` can be as little as the `tuple` the
generator already made a list of. So the choice is now which collections a relationship
*can* be held in rather than the one it cannot, and everything else is a list, as
`to_dao` already assumed when it handed a tuple over as one. The cascade was the second
half: the `NameError` left a half-executed module behind, and every later import of it
collided with the first association table it had already registered.

The general shape is the same as the name collision above and worth carrying: an
annotation the generator had never met before produces code nobody reads, so its first
reader is the interpreter importing the generated file. Both defects were one annotation
old.

The second job was one test. `InsideOf.compute_containment_ratio` was kept in its older
mesh-and-bounding-box form over `01e454d7b`'s, which counts the body's vertices against
the other's numeric bounds -- alone among that commit's numeric readings, since
`SupportedBy` and the region predicates both kept `numeric_global_transform`. The test
it failed is #244's own contract: containment is checked against every collidable body
on every detector tick, so it must reach its answer without building CasADi.

#### The four narrowing tests, and where they broke

What is left red is the four tests in `test_montessori_search_narrowing.py` the
convergence had already flagged for the developer. Bisecting them says exactly where:
all 27 tests in the file pass at `16c483635` and the same four fail at `03d9719d9`, the
merge of the hole layout fit (#236), which moves the fitted board 40 mm along y on
`tracy_pickup_demo` -- the square hole from `y=0.0569` to `y=0.0181` -- and every hole
with it.

Which fit is right is settled by the capture rather than by either branch's tests:
projected onto the picture, #236's hole centres land on the six real openings and the
pre-#236 centres land on bare wood, two of them off the holes entirely. So the code is
right and the docstrings' measurements are stale, which is what the convergence
suspected but could not show.

Re-measuring is not enough, though, and that is why it stays a call rather than a chore.
Against the corrected layout the cube stands 50.3 mm from the square hole and the
cylinder 51.6 mm, so no radius separates them; and the cylinder is 5 mm to that hole's
*left*, not its right. Two of the four tests have no reach and no two sides left to ask
about, so keeping what they demonstrate needs a different hole or a different pair --
a design call about the perception story, not a measurement.

#### The second `RecordedLook`, cleared by #292 (2026-09-06)

The last red job on #265 was the `Footprint` hazard below in a second instance, and it
is worth recording as one: the convergence brought two dataclasses called `RecordedLook`
into one package -- `perception/step_by_step.py`'s (the world, pipeline, frame, board and
viewpoint one look was taken in) and `perception/recordings.py`'s (one colour image a
rosbag holds with the depth published before it). ORMatic names a table after the bare
class name, so it emitted `RecordedLookDAO` twice, SQLAlchemy refused the second, and the
half-executed module left its tables registered for every later import to collide on --
13 failures and 8 errors from one duplicated word.

Renamed rather than added to `generate_orm`'s `ignored_classes`, and the reason matters
for the next instance. Ignoring `recordings.py` does not stop there: `BagReplay` holds a
`RecordedCamera`, so `watch_bag` joins the list, and so does every later holder of one --
an ignore list nobody is reminded to extend, whose omissions fail as this same cascade,
with the duplicate name still sitting there for the next class to hit. The rename is also
the only one of the two a session container can check at all, by grep rather than by
running a generation it cannot run.

`recordings.py`'s is now `RecordedImages`, with `RecordedCamera.looks()`/`look_at()`
following as `images()`/`image_at()`. `RecordedFrame`, the obvious name, is already
`scene_source.py`'s -- which is part of why this namespace collided in the first place,
and worth knowing before naming the next thing in it.

What makes it not recur silently: `test_montessori_orm.py` asserted that no mapped
Montessori class shares a name with an *upstream* one, which is the Footprint shape and
not this one. It now also asserts that no two of them share a name with *each other*.

Measured on CI, which is the only place it can be: the parent `e6c665cec` runs 13 failed,
742 passed, 8 errors, with 51 log mentions of the duplicated table; #292's `76e37a70`
runs 4 failed, 758 passed, no errors and no collision. The four are the narrowing tests
above, which fail identically on the parent.


### `scenario-domain-model` (#261)

Generalises `BenchmarkScenario`/`ScenarioRunner` and
`ExperimentResult`/`ExperimentsTable`/`TypstRenderer` into one dataclass
model (`Scenario`, `Goal`, `Condition`, `Perturbation`, `Metric`, `Report`,
`ScenarioRunner`) in `experiments/src/experiments/scenarios/`. Conditions and
perturbations belong to a run, not a scenario, so `icra-mechanism`'s
`knowledge-ablations`/`perturbations` add members rather than a second
scenario each. The trial log is structured objects, mapped later by
`episodes-recorded-through-ormatic`, never parsed back out of text.

First review round (2026-09-05, four threads, all four taken): deleted the
bespoke `ExecutionKind` for coraplex's existing `ExecutionType`; bound both
generic type parameters to the twin (`World`, `AbstractRobot`), which cost
`control_loop_experiments`' `BenchmarkScenario` a re-typed relationship to
`GiskardTester` and re-typed `ScenarioRunner` from
`Generic[WorldType, RobotType]` to `Generic[ScenarioType, WorldType]`; moved
the trial's clock onto `TrialLog.elapsed_seconds`. The container can run
these tests after stubbing `giskardpy_bullet_bindings` and ROS's `xacro` as
two empty modules on `PYTHONPATH` — worth knowing for every later item of
this track, since an earlier note here said the opposite.

Caveat for review: the migrated control-loop tests are `@pytest.mark.slow`
and excluded from default CI, so CI proves the migration imports and
aggregates, not that it still measures a motion — wants one manual run.

### `run-results-recorded-into-sql` (#262)

Extracted ~700 of #256's 7,124 lines: the recording trio
(`results_database.py`, `results_recording.py`, `sorting_results.py`) and
the three declarations that let ORMatic hold a segmind event at all. Cut off
`main`, additive only — `experiments/src/experiments/montessori/` exists on
neither `main` nor #244. Dangling docstring references (a nonexistent
`README.md`, a nonexistent demo script path) were repointed at what actually
exists on `main`. The database name was renamed
`franka_montessori_sorting_results` → `montessori_sorting_results` in review
(see Standing hazards above for the cost). Verified: `test_dependency_declarations.py`
and the three new test modules, all CI-only per the standing ROS limitation.

### `episodes-recorded-through-ormatic` (#271)

Based on #262 (replaces its `sorting_results.py`, keeps `ResultsDatabase`),
merging #261 (records the trials its runner produces — #261's own
`generate_orm.py` comment names this as the deferred decision). New package
`experiments/src/experiments/episodes/` (`episode.py`, `recording.py`),
beside `experiments/scenarios/` rather than inside `experiments/montessori/`,
since an episode is recorded by every scenario, not one demo's.

One `Episode`, one `RecordedTrial` per commit (memoised through one
`ToDataAccessObjectState` per episode, converting trials one at a time —
re-converting the whole `Episode` after each append does not work, since
`to_dao` returns a memoised DAO without re-reading collections). `FailureType`
is an empty `StrEnum` base for `icra-mechanism`'s `failure-taxonomy-and-typing`
to fill in — naming the four types here would be inventing that item's
taxonomy. `FailureResolution` does get its three members (retried, changed,
abandoned) because Experiment D's "how was this resolved last time" question
is answered from nothing else. Backends and conditions/perturbations are
recorded by name, not by enum member, since `backends-declare-their-capabilities`
(`icra-mechanism`) makes backends a class family rather than a fixed
enumeration.

Replaces `sorting_results.py` and its test; `ShapeInsertionExperience` exists
on no ancestor of this branch, so there is nothing here to replace for it.

### Why `episode-artifacts-recorded` is its own item, and why Experiment D exists

Added 2026-09-04, when the developer noticed the plan tracked no
long-term-memory *experiment* — the machinery
(`episodes-recorded-through-ormatic`/`episodes-queried-by-eql`) existed but
produced no number, since Experiments A–C only ask about the current scene.
`episode-artifacts-recorded` stayed separate from
`episodes-recorded-through-ormatic` rather than folding in, because the
artifacts need `simulated-camera-feeds-perception` and folding would put
this track's foot item — four other items wait on it — behind a later one. A
scope check found no in-flight branch sharing this work's paths, and a
duplicate-intent scan cleared #165's `DemoRecording`/`RecordedFrame` (a
`cramera` console replay buffer, not a per-episode video on disk).

Experiment D itself (its own experiment, simulation-only, questioning the
whole recorded corpus rather than retrieval) is `icra-evidence`'s decision;
the reasoning is recorded in that plan's roadmap since the items it produced
(`cross-episode-question-set-and-ground-truth`, `experiment-d-in-simulation`)
live there. This wave's contribution is only that `episode-artifacts-recorded`
exists and what it must supply: video (from `simulated-camera-feeds-perception`'s
`MujocoCamera` frames), the run's simulation data and world, and a
question-and-answer transcript, addressed by the episode's identifier rather
than held in its row.

### `episodes-queried-by-eql` (#278), as planned 2026-09-06

Cut off #271 rather than off `main`: `Episode`/`RecordedTrial` are what there is
to query, and they exist on no other ancestor. Three deep, then — #278 on #271
on #262 on `main` — which is what the readiness rule allows (#271 is open and
not a draft) rather than what it prefers.

New module `experiments/episodes/long_term_memory.py`, holding a
`LongTermMemory` over the `ResultsDatabase` #262 introduced:

- `answer(query)` runs an EQL query through
  `krrood.ormatic.eql_interface.eql_to_sql` and converts every row it returns
  into its domain object. Returning DAOs would make the SQL backend answer in a
  vocabulary no other backend uses, and it is the returning of domain objects
  that makes SQL one of the paper's four backends rather than a store the
  experiments happen to read.
- `recall_trials(episode_identifier)` is the one question a report asks.
- `report_on(episode_identifier, metrics)` rebuilds a `Report` from those
  trials.

Four decisions taken while planning it:

- **One `FromDataAccessObjectState` per answer**, so the trials of one episode
  come back pointing at one `Episode` object rather than a copy each. The
  read-side counterpart of the single `ToDataAccessObjectState` `RecordsTrialsToADatabase`
  already shares across a run's trials, and for the same reason.
- **A session per question, opened from the `ResultsDatabase` object it was
  given.** `open_recording` already records through the object it is handed so
  that a reader sees the rows a run is writing — only true of a shared
  connection for an in-memory database, which is what a run falls back to.
  Reading is held to the same rule, and `ResultsDatabase` caches its
  sessionmaker, so the per-question cost is one session rather than one schema
  build.
- **A `MeasuredTrial` protocol in `scenarios/report.py`**, declaring what a
  metric actually reads off a trial (`outcome`, `duration`), so `Metric`
  measures a live `Trial` and a `RecordedTrial` read back out of the database
  alike. `RecordedTrial` is deliberately kept apart from `Trial` — one is what a
  run holds while it runs, carrying live conditions and perturbations; the other
  is what goes into the database — so what they share is a protocol rather than
  a base class. Without it, every metric written from here on is trusted to have
  been given one of two unrelated classes.
- **The report is rebuilt by long-term memory, not by `Report` itself.**
  `experiments/scenarios/` describes how an experiment runs and knows nothing
  about a database; `generate_orm.py` ignores that package wholesale on exactly
  those grounds. `long_term_memory` joins `recording` in that ignore list for
  the same reason `recording` is there: it holds a database, which is not a
  record.

Tests record episodes through #271's own recorder into a SQLite file, then ask
for them back — the same objects, one shared episode, and a report whose metric
summaries and scenario name equal the ones the run's own report carried. The
rendered figure is deliberately not compared as well: `render_figure` is a pure
function of exactly those summaries and `test_scenarios.py` already pins it, so
a second assertion would fail only when the first already had. Queries are
kept to the shapes `test/krrood_test/test_ormatic/test_eql.py` already proves:
single-table column filters and many-to-one joins (`trial.episode.identifier`).
The to-many collections an episode holds — ticks, queries, insertion attempts —
are reached through association tables, and no test in this repository proves
EQL translates a join across one; nothing here depends on that, and finding out
belongs to whichever item first needs it. CI-only, per the standing ROS/`random_events`
limitation.

## 2026-09-08: refocused on the shared representation, and long-term memory cut loose

The developer's direction, in his words: focus the plans on *"that general
integrative aspect"* — that the same knowledge representation is used by the
control program and by the perception system, whatever the perception system
is, and that the control system takes the knowledge as constraints for an
optimization task, so that questions about the control system, the
perception system, the memory system and the temporal event segmentation are
all asked in one query language over one representation. And: *"reduce focus
on specific perception algorithms, that's not important anymore as we are not
showing we have better perception."*

### What changed here

- **The thesis** above, restated, and the plan `description` with it.
- **`simulated-camera-feeds-perception`** is retitled and rewritten as a
  frame source every perception backend reads, rather than as what makes
  perception testing honest. It exists so a backend can be swapped; it
  claims no detection result.
- **`episode-artifacts-recorded` lost its dependency on
  `simulated-camera-feeds-perception`.** This is the one edge whose removal
  changes who can work on what. The episode's video does not need the
  perception pipeline's frames — `MujocoVideoRecorder`
  (`semantic_digital_twin.adapters.mujoco_video_recording`) is already on
  `main` and attaches its own overview camera to the MuJoCo world. With the
  edge gone, the whole `long-term-memory` track — the episode model, the
  artifacts, the corpus, the self-model and control state, and the EQL
  querying over all of it — runs from `main` plus the episode model, with no
  dependency on lane 1 at all. That is what makes it a track one person can
  carry from today.
- **One new item** in that track. `episode-corpus-generated-at-scale` is the
  headless generator: seeded randomised scenarios run repeatedly, each
  episode recording its realized coraplex `Plan`, its segmind event log, the
  twin state, every query with its answer and latency, the typed failure and
  its resolution, and the rendered video — batched and resumable the way
  `batch_runner` already is, targeting thousands of episodes because
  Experiment D asks whether something has happened *before* and a corpus
  holding each situation once cannot answer that. (A second item was added
  and then folded the same day — see "the self-model item was wrong" below.)
- **`episodes-queried-by-eql`** now answers every bucket over recorded
  episodes, not only the temporal one.

### What did not change, and why

The perception lane is not cut. The demo has to see, and the classical stack
is what the resource comparison is measured against — a cost claim needs
something whose cost is known. What changed is that no *result* in the paper
is a perception result, so nothing downstream of the paper's argument waits
on the perception lane any more.

### How many episodes

Not fixed here. The generator's item says the target is thousands rather
than dozens and that the actual number is whatever it sustains overnight,
recorded rather than chosen in advance — a number picked now would be
invented, and the corpus size is a measurement like any other.

## 2026-09-08, later: the self-model item was wrong, and folded

`self-model-and-control-state-recorded` was added earlier the same day and is
now removed. The developer's question was the right one — *isn't that recorded
by ORMatic by default?* — and the answer is yes.

**What is already free.** `semantic_digital_twin`'s `generate_orm.py` maps the
whole package apart from ten ignored classes, and none of them is `World`,
`Body`, `Connection`, `DegreeOfFreedom` or `DegreeOfFreedomLimits` — so the
robot's kinematic structure has DAOs today. `giskardpy`'s maps its whole
package apart from `giskardpy.qp.solvers`, so `MotionStatechart`, its tasks
and monitors and the terminal `EndMotion`/`CancelMotion` nodes are mapped too.
The dependency chain already reaches both: `experiments` declares
`coraplex.orm.ormatic_interface`, `coraplex` declares
`giskardpy.orm.ormatic_interface`, and `giskardpy` declares
`semantic_digital_twin.orm.ormatic_interface`. So an `experiments` class can
hold either and it maps, with no generation change at all. And the
*working-memory* spelling of the self-model bucket needs nothing whatever:
"how many joints do you have" is a query over the live twin today.

**What was actually missing**, checked against #271's own `episode.py`:
`Episode` carries the scenario name, execution type, condition and
perturbation names, an identifier and a timestamp; `RecordedTrial` carries
outcome, duration, ticks, queries and insertion attempts; `InsertionAttempt`
carries the realized coraplex `Plan` — the robot plan, already there. Neither
the world an episode ran in nor the motion statechart a trial ran is
referenced by any of them. That is a field or two, not an item.

**So it folded into `episodes-recorded-through-ormatic` (#271)**, by the
mechanical scope rule rather than by taste: `git ls-tree origin/main --
experiments/src/experiments/episodes/` is empty, so #271 introduces the file
the change would edit, and work that only modifies an unlanded pull request's
own file is that pull request's work. This is the same shape as the
2026-09-04 amendment that gave the model `FailureResolution`, and its notes
now carry both references.

**Left to the developer**, recorded on that item rather than decided here:
whether each episode stores a `World` of its own or references one shared
robot model. A world per episode answers a question about a run whose robot
differed; at the scale `episode-corpus-generated-at-scale` targets it may be
disproportionate.

The general lesson, worth carrying: in this workspace ORMatic maps a package
*wholesale*, so "does this need recording infrastructure" is almost always
already answered — the real question is only ever whether anything
*references* the mapped class. Check the ignore list and the model before
writing an item that assumes mapping work.

### `episode-artifacts-recorded` (#294), as planned 2026-09-08

Cut off #271, not off `main` and not off #278: `Episode` and `RecordedTrial` are what
an artifact is addressed by, and they exist on no other ancestor. #278 is a sibling on
the same parent rather than a dependency — this item does not query anything back out
of the database. #271 is open and not a draft, so it counts as ready to build on, the
same reading #278 was cut under.

**The parent already built the reference, so `episode.py` is not touched.**
`Episode.identifier` on #271 is documented in as many words as "what addresses this
episode outside the database, where its video, its simulation data and its transcript
are kept". The item's "a row references one rather than holding it" is therefore
already satisfied by the parent, and this branch adds no field to the episode. Its only
edit to a file another branch also touches is `generate_orm.py`'s ignore list, which #278
also appends to — two appended blocks in the same region, a textual meeting rather than a
design one.

New module `experiments/episodes/artifacts.py`, holding:

- `ArtifactDirectory` — where every episode's artifacts are kept, resolved from an
  environment variable with a built-in default, exactly as `ResultsDatabase` resolves
  where the rows go. Not derived from the database URI, because the default database is
  Postgres and has no filesystem place to sit beside; "beside the database" is a
  relationship between two configured locations, not a path inside one.
- `EpisodeArtifacts` — one episode's own directory, named by its identifier, with
  `keep_video`, `keep_file` and `keep_transcript` writing into it and `video`,
  `run_files` and `transcript` reading them back.
- `Transcript` — the episode and the trials it is rendered from, with `render()`
  producing the readable document. A dataclass rather than a formatting function, so
  what a transcript is made of is named rather than assembled at the call site.
- `EpisodeArtifact` — a `StrEnum` of the three names an episode's artifacts are kept
  under, so no filename is spelled twice.

Three decisions taken while planning it:

- **The store keeps the run's files; it does not serialize a world.** The item names
  "the run's own files, the world it built and the plan it realized" as the simulation
  data. The realized plan is already a database row (`InsertionAttempt.plan`), and
  whether an episode references a `World` is recorded on #271 as the developer's open
  call. So what is added here is the keeping of files a run produced — the MuJoCo scene
  a build already writes, among them — rather than a world serializer this item would
  have had to invent.
- **`recording.py` is not touched, so no run is wired to write artifacts here.** The
  seam is `Episode.identifier`, and the writer is
  `episode-corpus-generated-at-scale`, whose own notes already name the video
  `MujocoVideoRecorder` rendered as one of the six records it writes. Extending
  `EpisodeRecording` here would put a MuJoCo world in the path of this item's tests for
  no gain and add a conflict surface with #271 and #278.
- **`RecordedVideo` is imported under `TYPE_CHECKING` only.** Encoding is
  `RecordedVideo.write`'s already, so this module needs the name as a type and never as
  a runtime import — which keeps the transcript and the file-keeping usable without
  MuJoCo present.

Tests record a two-trial episode and read all three back: the video (frames encoded to
`.mp4`, the path `RecordedVideo.write` already proves in an always-on
`semantic_digital_twin` test), the run's own files, and the transcript, whose rendered
text carries every query of both trials with its answer. CI-only, per the standing
ROS/`random_events` limitation this track has recorded throughout.

**A tooling defect found while bootstrapping it, left unfixed here.**
`.claude/hooks/plan_item_bootstrap.py`'s `ITEM_FIELD_INDENT` is four spaces, while
every `plan.yaml` in `.claude/personal/plans/` indents an item's fields by two. Its
`open`/`record` patch therefore writes `branch`, `pull_request_number`, `status` and
`session` one level too deep — inside the preceding folded scalar or list — and
`save-plan.sh` rejects the result as unparseable YAML. This item's manifest fields were
written directly instead. Unfixed on this branch because it is `.claude/` tooling and
nothing to do with episode artifacts; it blocks every `plan-item-kickoff` and
`plan-item-resolve` bootstrap until it is fixed.

### `montessori-scenarios` (#296), as planned 2026-09-08

The memo's scenes and its four scripted temporal scenarios, written as instances of
#261's domain model. New module `experiments/montessori/scenarios.py`, holding the
layouts, the scenarios, their goals and steps, and the lighting perturbation; the
scenarios live in `experiments/montessori/` rather than beside `experiments/scenarios/`
by the same reasoning that put the episode model in `experiments/episodes/` — an episode
is recorded by every scenario, but these scenarios are one demo's.

**Cut off #202 with #261 merged in, not off #265, and that is the one decision here
worth arguing.** The item's recorded dependencies are `scenario-domain-model` (#261) and
`integrated-simulation-pipeline` (#265), and the obvious reading is to base on #265.
Measured rather than assumed: #265's merge base with `main` is 74 commits and 114 files
behind the `main` that both #261 and #202 are built on, so merging #261 into #265 does
not merge a scenario model — it advances the whole convergence branch onto that `main`.
Four files conflict (`mapped_variable.py`, `world.py`, `geometry.py`, `test_color.py`),
every one of them a file #261 never touched and #265 hand-resolved during its own
convergence pass, and at least one breakage follows silently: `memoize` has moved from
`krrood.utils` to `krrood.patterns.caching`, which #265's `world.py` still imports the
old spelling of.

That advance is #265's own work, and the convergence pass already recorded the principle
it violates — seven branches were merged *into* #265, each at its own tip, "never
sideways into each other, which would have paid the same conflict set twice". Basing
this item on #265 and merging #261 in is exactly that sideways merge.

What these scenarios need is the Montessori world (`world.py`, `semantics.py`,
`pieces.py`, `hole_geometry.py`) and the scenario domain model. #202
(`montessori_perception_on_main`) carries the first and is current with `main`; #261
carries the second and is current with `main`; the two merge with **zero conflicts**.
Nothing here reads the perception pipeline, the event monitor or the predicates, so
nothing here needs #265 — and #265 merges this branch later, the way it merges every
other tip. The `depends_on` edge to `integrated-simulation-pipeline` is left as recorded
rather than rewritten here: which edges a plan declares is the plan's call, and the
question is raised on the tracking issue rather than answered on a branch.

**Design.** A `PieceLayout` is where the pieces stand, and it is the parameter every
scene shares rather than a scene of its own: `randomized` over a seed places all four of
`KNOWN_PIECES`, `partial` places a named subset (the two- and three-piece scenes), and
`nearly_ambiguous` places the cube and the cylinder at one distance from a stated
viewpoint. The near-ambiguity is real and is the set's own: `pieces.py` gives the cube
and the cylinder the same `CYAN_HUE`, so at one depth neither colour nor depth separates
them and only the outline does.

The lighting change is a `Perturbation`, not a scene. #261's review settled that
conditions and perturbations belong to a run rather than to a scenario, so a scene that
differed only by its light would be a second scenario for a change the model already
has a place for.

The four scripted scenarios differ by their steps rather than by their worlds: nothing
happens; the robot picks a piece up and puts it down; an external body pushes a piece
while the robot is idle; a piece is in the gripper when the trial ends. Each carries a
`PieceLayout`, so the scenes and the scripts compose rather than multiplying.

The robot is a bound generic parameter, as #261's review decided, so the scripted
scenarios stay generic in it and the concrete bindings pick the robot: the demo's
scenarios bind `Tracy`, and the tests bind the test dataset's `SyntheticFixedArmRobot`,
which parses from a URDF in the repository and therefore builds headless where
`tracy_description` is not installed.

`generate_orm.py`'s ignore list gains these classes for the reason #261 gave for its
own: a scenario describes how an experiment is run, not what it recorded. That is an
appended block in the same region #261, #278 and #294 append to — a textual meeting, not
a design one.

**What the session container can and cannot do, corrected.** The standing note that
nothing on these branches runs in a session container is now too strong, and the
correction is worth more than the note was: `random_events` and `probabilistic_model`
install from wheels, and with `mujoco`, `casadi~=3.7.0`, `daqp`, `manifold3d`,
`plyfile`, `urdf_parser_py` and `rustworkx` beside them, `MontessoriWorld()` builds — six
holes, seven shapes, six landing regions — against a stub for `xacro` and a permissive
stub for the compiled `giskardpy_bullet_bindings`, which is the one piece that genuinely
will not build. So the world, the layouts and the goals are checkable here; the collision
checker is not, and CI stays the authority on anything that reaches it.

**Two refinements the implementation settled, 2026-09-08.** The near-ambiguous layout
takes the *closest* of the placements it draws at the matched depth rather than the
first: sharing a depth is what the scene is built for, but a scene where the two also
stand half a metre apart is not confusable, and picking the nearest valid candidate
makes it confusable without a separation nobody chose being written down. On the default
area it stands them 29 mm apart at one depth. And every height in the module is measured
in the world root frame against one `TABLE_TOP_Z`: the first pass measured a piece's own
height above the table while the viewpoint's was absolute, which cancelled in the
equal-depth comparison the test makes and would have been wrong for anything else
reading a depth. A test now pins the frame by asserting a built piece's lowest point
sits exactly on the table.

**The first review round, 2026-09-08, and what it changed about #261's model.** Two
comments, both on `experiments/scenarios/scenario.py` — which is #261's file, carried
here by the merge, not this branch's own. Taken on this branch rather than on #261
because that is where the review was left and #261 is already promoted upstream; the
reply says so, and says the word if he would rather it moved.

`Goal` is now a krrood `Predicate`: `is_reached` is its `__call__` and each goal states
its own `_verbalization_fragment_`. The mandatory half needs no enforcement of ours —
`Verbalizable._verbalization_fragment_` is abstract, so a goal that omits one cannot be
instantiated at all, which a test pins.

The consequence is the part worth carrying, because it reshapes the model rather than
one class. A predicate is called with no arguments, so its operands are its fields, so
the world a goal judges has to be a field of it — and a goal can therefore no longer be
one instance declared once on a scenario, since the world does not exist until the trial
builds it. `Scenario.goal` moved from a field to a method beside `steps(world)`, the
runner reads it through `Predicate.__bool__`, and the four scripts here lost their
`field(init=False)`/`__post_init__` pairs. `MotionRanToItsEnd` on the migrated
control-loop benchmark took the same shape.

`Condition` became `ScenarioCondition` in the same commit, with every reader.
`ConditionApplied` kept its name: it is the log event, not the thing.

Only the rename thread was resolved. The `Goal` thread is answered but left open,
because the reply asks a question of its own — whether the change should have landed on
#261 instead.

### `simulated-camera-feeds-perception` (#298), as planned 2026-09-08

The frame source, not a detector. Refocused with the plan the same day: a backend can only
be swapped for another if every backend reads its input from one place, so what this item
owes is an `RgbdFrame` rendered out of the twin — nothing about detection quality, which the
paper no longer claims.

**Cut off #265, and here that is uncontroversial.** What a simulated frame is fed to is the
perception pipeline, and `MontessoriPerceptionPipeline`, `SceneToSearch` and `SurfacePass`
exist on no other ancestor. #265 is open and not a draft, so the readiness rule counts it as
ready to build on — the same reading #278 and #294 were cut under. This is not the case
`montessori-scenarios` argued against: nothing is merged *into* #265 here, so none of that
item's sideways-merge cost applies.

**Nothing is wired to a vision-language backend, because none exists.** The item's notes name
"a vision-language backend and a visual-question-answering backend"; a scan of the workspace
finds neither, and `icra-mechanism` owns both — `backends-declare-their-capabilities` makes a
backend declare what it answers, and `vlm-baseline-harness` builds the model arm. What this
item can honestly deliver towards that sentence is the one frame type they will read, which
is what it delivers. Recorded rather than raised as a question, since the plan already places
that work elsewhere.

**What already exists, and is therefore not built here.** The four conversions are the whole
of the new code; everything else the item's notes ask for is already in the tree and was
checked rather than assumed:

- *The colours and finishes.* `pieces.py` derives `KnownPiece.color` from the hues #239
  measured (`CYAN_HUE = 86`, `YELLOW_HUE = 21`), and `world.py` already renders every loose
  shape and the board in them (`_SHAPE_COLORS`, `BOARD_COLOR = color_of_hue(MEASURED_BOARD_HUE)`),
  with `finish` stated on the table. So "stated colours and finishes come from the values #239
  measured" is a property of `MontessoriWorld` that this item consumes, not one it adds.
- *The rendering.* `MujocoSimulator.capture_rgb` and `capture_depth` already render from a
  named camera; `MujocoVideoRecorder` already shows how a headless mirror is built
  (`MujocoSim(world=..., headless=True)`, `MUJOCO_GL=egl`, `mj_forward` before each render).
- *The surfaces.* `WorkspaceSurface.of(supporter, reference_frame)` already reads a surface
  off the twin's own `HasSupportingSurface`, so the simulated rig's table and lid are read
  from `MontessoriWorld` rather than restated the way `recorded_setup.py` has to restate the
  real rig's.

**The four conversions, which are what the item actually is.** Each is a place the twin's
vocabulary and the pipeline's differ, and each is pinned by a test rather than by a comment:

- *Intrinsics.* A `MujocoCamera` states a vertical field of view and a resolution; a frame
  carries pinhole `CameraIntrinsics`. `focal_length_y = (height / 2) / tan(fovy / 2)`, with
  `focal_length_x` equal to it since MuJoCo's `fovy` implies square pixels, and the principal
  point at the image centre. Written as a classmethod on `CameraIntrinsics`, which already
  owns the other way in (`from_camera_info_matrix`), rather than as a helper beside the
  camera — one operation, one owner.
- *Depth.* MuJoCo returns the far-plane distance for a pixel showing nothing; `RgbdFrame`'s
  contract is that zero marks a pixel with no reading, and `carries_depth`, `depth_at` and
  every deprojection read it that way. Far-plane readings are therefore zeroed, or a look at
  empty air would measure the sky as a surface.
- *Colour order.* MuJoCo renders RGB and `RgbdFrame.color` is OpenCV's BGR.
- *Pose.* A MuJoCo camera looks down its own -z with +y up; the optical frame a frame's
  `reference_frame_T_camera` is stated in has +z along the axis it looks down and +y down the
  picture. The two are a half turn about x apart, and getting it wrong flips every *left of*
  the pipeline reports without failing anything else.

**Written into `generate_orm.py`'s ignore list**, for the reason #261, #278, #294 and #296
each gave for their own: a camera renders a frame, it is not a record, and the module holds a
live simulator handle ORMatic could not map anyway. That is an appended block in the same
region those four append to — a textual meeting, not a design one. The `RecordedLook` hazard
was checked in the other direction too: `SceneCamera` is already taken by
`graph_of_convex_sets/volume_figure.py`, so the class is `SimulatedCamera`.

**Tests, and where the risk in them sits.** The four conversions are each asserted against the
definition rather than a literal — the intrinsics by projecting a body's known world position
and reading the render at that pixel, the depth by deprojecting the board's centre pixel back
to the lid height `WorkspaceSurface` states, the colour by comparing to `KnownPiece.color`
through `DetectionColor.to_bgr`, the pose by reading a direction the scene's own layout fixes.
The item's own stated criterion — a simulated scene with the board and four pieces reports
every piece once with the right category — is the fifth and the one that can genuinely come
out red, because it measures detection on rendered images and nothing has ever run the
detectors on one. It is written as the item asks; if it fails, what is reported is the
measurement and the diagnosis, not a weakened assertion.

CI is the authority, per the standing ROS/`random_events` limitation this plan has recorded
throughout, with the addition that offscreen MuJoCo rendering needs an EGL context a session
container may not offer either.

#### What the implementation found, 2026-09-08

**The frames work, and every conversion is pinned by a measurement rather than by a
comment.** Rendering a `MontessoriWorld` through a camera placed where the real one
stands produces intrinsics of `focal_length = 1117.04` against the captures' own
`1117.02`; the point read back out of a piece's pixel stands within two millimetres of
where the twin put it; and the depth read at the board's middle is the lid height
`WorkspaceSurface` states. The four conversions are:

- *Intrinsics.* `focal_length = (height / 2) / tan(fovy / 2)`, both axes equal, with the
  principal point at `((width - 1) / 2, (height - 1) / 2)`. The pixel-centre convention
  is not a detail: measured against a rendered marker, the edge convention is off by
  0.55 px and the centre convention by 0.05 px.
- *Depth.* MuJoCo answers with `model.stat.extent * model.vis.map.zfar` for a pixel
  showing nothing, and renders it in single precision, so the value comes back a little
  past the distance the model states -- 43.66174 against a stated 43.660254 in the
  probe. Anything at 0.999 of the far plane or beyond is therefore zeroed, which is what
  `RgbdFrame` means by *not measured*.
- *Colour order.* MuJoCo renders RGB; `RgbdFrame.color` is OpenCV's BGR.
- *Pose.* A half turn about x, `diag(1, -1, -1)`.

One thing the tests had to be corrected about, and it is the kind of mistake the whole
chain being asserted at once catches: a look measures the face it lands on, not the
middle of the solid behind it, so reading back the pixel a piece's own centre projects to
answers three and a half millimetres further out -- exactly the parallax between the two
heights over the twenty centimetres the piece stands from under the camera. The tests ask
about the middle of the face a piece shows instead.

**The camera stands where the real one does, and every number saying so is read off the
captures rather than chosen**: 0.935 m above the table, 51.6 degrees, 1920 by 1080. Each
is a constant with a test pinning it to `tracy_pickup_demo`'s own frame, so none can
drift from the rig it stands in for. The one deliberate difference is that it looks
straight down while the real camera is about eleven degrees off vertical; the picture is
turned the real one's way (its right is the world's negative y) so a direction read off a
simulated look reads as it does off a capture.

**The item's own criterion does not pass, and the cause is not in this branch.** A look
at the simulated scene reports every kind of piece standing on the table -- so the stack
that reads a capture reads a rendering, which is what the item is for -- but it reports
eight things where four stand, and does not find the board at all. Both are one cause: a
`Region` is exported to MuJoCo as a visible geom, so the board's six `ShapeSortingHole`
regions render as solid coloured markers filling its holes. They wear the very hues the
piece detectors search for, which is where the four extra reports come from; and
`BoardDetector` finds a board *by the openings cut through it*, which a board with its
holes filled in no longer has.

That is a property of the twin, not of the frame source, and the fix is a design call
this item does not get to take: `MujocoGeomConverter` puts a region's shapes in the same
geom group as real visual geometry, so a camera cannot simply decline to draw them, and
making regions invisible would change what every MuJoCo viewer and every recorded video
shows. `test_every_piece_on_the_table_is_reported_once_with_its_own_category` is
therefore written exactly as the item states it and marked expected-to-fail, strictly, in
the same style `test_montessori_detection_on_captures.py` already uses -- the day regions
stop being rendered it reports the mark as stale rather than quietly passing.

**Open question for the developer, raised by this item:** should a `Region` be rendered
into a simulated picture at all? It is a named volume of space rather than a thing, and
anything looking through a camera in the twin currently sees it as an object. Answering
*no* is one flag at the region conversion site and is what would let this item's own
criterion pass.

**A second finding, left alone for the same reason.**
`SceneToSearch.expected_pieces` reads every `MontessoriShape` inside the searched
stretch and looks each up in `KNOWN_PIECE_BY_CATEGORY`, which holds only the four pieces
perception knows -- so a look at an unthinned `MontessoriWorld`, which also spawns a disk
and a sphere, raises `KeyError` before anything is detected. It is a defect of the merged
tree rather than of this item, and per the one-root-cause-per-branch rule it belongs in a
bug fix of its own. This item's tests work on a scene holding one of each piece
perception knows, derived from `KNOWN_PIECE_BY_CATEGORY` rather than named by hand.

**Verified:** `test_montessori_simulated_camera.py` 11 passed and 1 xfailed;
`test_mujoco_rendering_backend.py` 4 passed; `test_mujoco_video_recording.py` 16 passed
with `CI=true`, which is what actually runs the extracted backend choice through the
recorder.

**One shared piece of tooling moved.** Choosing MuJoCo's offscreen backend was written
inline in `MujocoVideoRecorder.start`, and a second renderer needs the same four lines
and the same reasoning, so it is now `multi_sim.select_offscreen_rendering_backend()`
with the backend names a `StrEnum` and `MUJOCO_GL` named once. The recorder calls it.

**On the container, correcting the note again.** With `mujoco`, `casadi`, `opencv`,
`trimesh`, `usd-core`, `rtree` and the `random_events` wheel's compiled library beside
the workspace sources, and stubs for `xacro` and `giskardpy_bullet_bindings`, a
`MontessoriWorld` builds, a MuJoCo mirror renders through EGL (after `libegl-mesa0` is
installed) and the whole perception pipeline runs -- which is how every number above was
measured. What still needs CI is the ORM generation, which needs ROS. Note the
interpreter: the workspace needs Python 3.12, and `dataclasses.make_dataclass(module=)`
is what fails first on 3.11.

## 2026-09-08: the four narrowing tests, and the fact that settled all four

The four failures in `test_montessori_search_narrowing.py` came to this session already
diagnosed: the hole layout fit (#236) moves the board 40 mm along y on
`tracy_pickup_demo`, projecting both layouts onto the capture shows the fitted centres
landing on the six real openings and the pre-#236 centres on bare wood, so the code was
right and the docstrings were stale. What was open was which hole and which pair each
test should read instead, since two of them had been shown to have no reach and no two
sides left.

**The premise that "two of the four need a new pairing" was itself too narrow, and one
measurement settled it.** Measured over all six holes rather than the square one, the
left-right axis separates the cube from the cylinder from *no* hole on this board, read
from the camera or from the world, because no hole's y lies between the two pieces (cube
0.0634, cylinder 0.0231; holes at 0.0182, 0.0189, 0.1053, 0.1060, 0.1960 and 0.1968).
Only front-back in the world and up-down in the picture separate them, and every hole
affords both. So it was three tests reading a left-right direction, not two — and the
fourth was never a test problem, but the production statement's own `LeftOf`.

That one fact chose every replacement, rather than each test being re-fitted on its own:

| test | now reads | measured |
|---|---|---|
| which way a piece lies, from where it is seen | `Above` / `Below`, square hole | cube 18.6 mm up the picture, cylinder 45.4 mm down |
| the two sides of a hole | `InFrontOf` / `Behind`, square hole | cube 16.2 mm in front, cylinder 49.1 mm behind |
| how far a reach was asked for | `Near` the triangle hole, 0.07 and 0.12 | cube 50.0 mm, cylinder 93.8 mm |
| the demonstration down to the cube | unchanged; the statement asks `Above` the square hole | — |

Two of them say what they were written for *better* than before. The two sides of a hole
paired `InFrontOf` with `RightOf`, which is two axes rather than two sides of one; it is
now one axis. And reading up and down from the camera is the sharper case for the
viewpoint mattering at all, since in the world both pieces stand the lid's own 15.0 mm
above every hole and neither is above the other — so the direction separates them only
when read from where the camera stands, which is exactly that test's claim.

The reach test moved hole rather than radius because the square hole holds the two pieces
1.3 mm apart (50.3 and 51.6). The triangle hole was taken over `circular_hole_1`, whose
gap is wider still (17.1 and 74.8), because it is named through `HOLE_NAME_BY_CATEGORY`
where the circular hole would have to be addressed by a raw string. 0.05 was not reusable
as the near radius: the cube stands at 50.04 mm and would land inside it.

**Standing hazard corrected, again.** "Nothing on these branches runs in a session
container" is wrong for the montessori perception suite. A python3.12 venv with the
workspace sources, `random_events` installed editable, and `casadi~=3.7.0` (3.8 breaks
`FunctionBuffer.set_res`) runs the whole pipeline; every number above was measured there
and reproduces the recorded ones exactly. What is still blocked is `pytest` itself, in
the conftest's ORM generation (`CouldNotResolveType: QPControllerConfig`, walking
giskardpy), so the four behaviours were driven from a script that mirrors the test bodies
instead. That also kept the fix honest: no test file was open while the measurements were
being taken.

**Left red.** The experiments job still carries the duplicate `RecordedLook`, which #292
fixes against this branch and which had already been decided before this session — the
manifest's own record of it is what corrected this session's stale reading of it as an
open call. #292's `76e37a70` ran 4 failed, 758 passed, no errors, and those four were
these tests, so #292 plus `dae41889c` is what takes the job green.

## 2026-09-08 (later): the hole bodies were never the fitted centres

The section above is right that the fitted layout is the one landing on the six real
openings, and wrong about which objects it measured. `board_holes_in` never used the fit
at all: it added the board mesh's **own, unscaled** hole offsets to the fitted board
pose. Since #236 the board is found at `BOARD_SCALE_AGAINST_THE_MESH` = 0.865, so those
offsets spread the holes about fifteen percent too wide. On `tracy_pickup_demo` the
square hole body stood 12.1 mm from the hole the same look reported, the disk hole 12.7
mm. Every hole y quoted above — 0.0182, 0.0189, 0.1053, 0.1060, 0.1960, 0.1968 — is a
displaced body. Placed where the look found them the six stand at 0.0299, 0.0306, 0.1053,
0.1059, 0.1838, 0.1845.

**So the fact that chose every replacement was an artefact.** The square hole at 0.0299
*does* lie between the cylinder at 0.0231 and the cube at 0.0634, so left and right do
separate the two pieces about it; and the 1.3 mm that ruled the square hole out of the
reach test becomes 41.2 mm against 49.4 mm. The four tests were never stating what the
capture does not show — they were reading it from a place 12 mm off.

`board_holes_in` now places each hole where the look put it, which is the one fit rather
than a second reading of the mesh at another size; `hole_names` takes the categories it
reads rather than the footprints it was handed, so a detection can be named by it too.
Pushed on #292 as `73b0c1cb4`, with
`test_montessori_recorded_setup.py::test_a_hole_body_stands_where_the_look_found_that_hole`,
which fails on the parent at 12.1 mm and 12.7 mm. Three of the four narrowing tests come
green from that commit alone, against the pre-`dae41889c` file.

**`dae41889c` is kept, not reverted.** Its four choices all still hold once the holes
move, and two of them read better than the originals for the reasons the section above
gives — one axis rather than two, and the viewpoint mattering. What moved is every
millimetre it quotes, requoted in `8b8914c74`: cube above the square hole 19 → 21 mm,
cylinder below it 45 → 43, cube in front 16 → 19, cylinder behind 49 → 47, the two pieces
from the triangle hole 50 and 94 → 51 and 93, cube above the triangle hole 25 → 27,
cylinder below it 39 → 37. One claim is replaced rather than requoted:
`look_for_the_cube_on_the_lid` said left and right tell the two apart from no hole on
this board. Up and down are still the wider margin from the square hole — 21 and 43 mm
against the 7 mm the cylinder stands from it across the picture — so the statement keeps
asking for `Above`, on the honest reason rather than the artefact.

**The lesson worth keeping.** Two sessions verified the fit and then measured the bodies,
and neither noticed the two were different objects. Wherever a thing is derived twice —
once by a fit and once from the model the fit was of — the check that they agree is the
test to write, and it is one assertion: `board_holes_in`'s output against `board.holes`.

**Standing hazard corrected once more.** `pytest` is *not* blocked in a session
container: `CRAM_ORM_BUILD=never` skips the conftest's ORM generation, and
`test_montessori_search_narrowing.py` then runs in 75 s. With the venv the section above
describes, plus `objgraph`, `pytest>=7,<8` and `pytest-order`, 506 of the montessori
suite pass; the 15 that fail are `test_montessori_orm.py` and
`test_montessori_results_database.py`, which need the generated interfaces and a
database, and they fail identically with any change stashed. So a montessori perception
change can be run end to end here before it is pushed, tests and all.

### The first review round on #298, 2026-09-08: a region is drawn see-through, a camera draws none

The developer's answer to this item's open question, in his words: *"make them
transparent regions and make it a toggelable thing"*.

`RegionAppearance` on `MultiSimBuilder` says how much of a region a simulator draws.
`TRANSPARENT` is a share of the opacity the region itself states (0.3 of it) and is the
default everywhere a world is built or a region is spawned at runtime; `HIDDEN` builds
the region's body and none of its geometry, so what the world hangs off a region still
has a frame to hang off. The share is carried into the one place a shape becomes a geom
rather than applied at each call site, so the builder and the spawner fade a region the
same way and a body's own geometry is untouched. `MujocoSim(region_appearance=...)` is
the toggle. `SimulatedCamera` sets it to `HIDDEN`, because the real camera it stands in
for sees no volume of space -- one word to change if the picture should show them.

**What the fix uncovered is worth more than the fix.** Measured on the reference scene,
one of each piece perception knows standing on the table:

| regions | reported | board |
|---|---|---|
| drawn solid (the old behaviour) | 8 -- two "cubes" and a "cylinder" at the board's own holes, plus the four pieces' places | not found |
| drawn see-through | 5 | found, 6 holes |
| not drawn (the camera's default) | 5 | not found |

Reading the places rather than the counts is what settles it: with the markers drawn,
the two `cube` reports stand at the board's holes (`-0.382, -0.093` and `-0.426,
-0.091`), not at the cube (`-0.15, -0.13`), whose place is reported `cylinder` in all
three columns. So `test_every_piece_the_world_places_on_the_table_is_found` was passing
on an artefact: the cube it counted was the square hole's own marker. It is now marked
expected-to-fail beside the item's stated criterion, strictly, and the two mark two rungs
of one ladder -- every kind found, and every piece once with its own category.

Two things the twin would have to say for either to pass, neither of them the frame:

- **The pieces it builds are not the size perception measured off the real ones.** The
  cube is 22.4 mm across where `KnownPiece` states 30, the cylinder 22.4 against 28, the
  triangular prism 25.2 by 29.4 against 37 by 32, the rectangular prism 15.4 by 29.4
  against 20 by 40. No outline fits well at those sizes, so which one wins a place is a
  coin flip -- and it is why the cube's place is won by the cylinder. Which of the two
  sizes is the real piece is the developer's call: the world's shapes are built from the
  board's own holes, and `pieces.py` was measured off the captures.
- **The board's holes are cut through an 80 mm blank** (`BOARD_SCALE.z`), so looking down
  one shows 80 mm of wall lit in the board's own colour rather than the dark opening a
  capture shows. `BoardDetector` finds a board by its openings, and a render has none.
  This is also why the board *is* found when the regions are drawn see-through and not
  when they are hidden: the markers were the only thing giving the holes an outline.

**Verified** in the session container, on the rebased branch: `test_montessori_simulated_camera.py`
12 passed and 2 xfailed, `test_region_appearance.py` 4 passed, `test_mujoco_video_recording.py`
16 passed with `CI=true`, `test_mujoco_rendering_backend.py` 4 passed, `test_mjcf.py` 10 passed.

### The second review round on #298, 2026-09-08: the pieces are the size they were measured to be

The developer's answer, in his words: *"scale the objects to the known pieces, and remove
the marker boarders, this should look like the real thing for the camera"*, on two threads.

**The marker half needed nothing** -- `SimulatedCamera` already builds its mirror with
`RegionAppearance.HIDDEN`. What the comment settles is the open question the first round
left: the camera's default was a guess and is now the developer's own answer, so it stays
hidden.

**The size half changed the world, not the camera.** A loose shape was built as a fixed
0.7 of the hole it drops through, and `pieces.py`'s own module docstring already says why
that is the wrong source: *a piece is cut smaller than the hole it drops through, so the
hole's footprint is the wrong size to recognise a piece by or to build one from*. So the
size now comes from `KnownPiece` and only the cross-section from the hole. Built: cube
30.0 mm, both cylinders 28.0, rectangular prism 21.0 by 40.0, triangular prism 31.7 by
37.0, every one of them 30.0 tall.

One scale for both axes, which is the decision worth recording rather than the numbers. A
per-axis scale onto the piece's own bounding box looks obvious and is wrong here: the
hole's triangle is a side-42 mm one pointing along `+x` and the measured piece's a
side-37 mm one pointing along `+y`, ninety degrees apart, so per-axis scaling squashes the
hole's outline into neither shape and comes out 3 per cent *wider* than the hole it has to
fall through. Building from `KnownPiece.outline` directly is wrong for the same reason
from the other side: it would put the piece in its own local frame rather than the hole's,
and `insertion_pose_relative_to_hole` releases a piece over its hole unrotated *because*
the two share a frame -- a contract
`test_orientation_sensitive_shape_matches_its_holes_footprint_orientation` already pinned.
A uniform scale keeps both. What the two are matched by is `cross_section_size`, which
`MontessoriShape` and `ShapeSortingHole` already agreed on the meaning of;
`KnownPiece` and `HoleFootprint` now answer it too.

**Two consequences, both reported rather than hidden.** Clearance against the hole goes
from 0.70 everywhere to between 0.70 and 0.95, tightest on the rectangular prism at about
a millimetre a side; the 0.7 carried a docstring recording that it was tuned against
insertion pass rates over 20 runs, and what replaces it is the real set's own clearance
rather than a chosen number -- a sorting run is what would settle it and no session
container can run one. And both circular shapes are now one size, since the set holds one
cylinder, so no hole can be resolved by size at all: `hole_for` already preferred the name
pairing, and that preference is now the only thing that works.

#### What it fixed, and the defect it exposed instead

At the measured sizes **both detectors read all four pieces within a millimetre of where
the twin put them, each with its own category** -- the cube's place is no longer won by the
cylinder's outline, which is what the first round found the old test passing on. And then
the scene reports one of them, because of the arbitration afterwards:
`Occupancy.keep_one_detection_per_place` drops a place two readings claim unless one leads
the other by `CompetingExplanations.required_lead` (0.075), **and it drops the holder as
well as the claimant**.

| piece | the two readings | outcome |
|---|---|---|
| cube | 0.7121 and 0.7121 | both dropped |
| rectangular prism | 0.6596 and 0.6596 | both dropped |
| triangular prism | 0.7480 and 0.7433 | both dropped |
| cylinder | 0.8635 and 0.8464 | kept |

On `tracy_pickup_demo` the same two detectors read 0.5821 against 0.4669 and 0.4726
against 0.4495, far enough apart for one to lead, and all four pieces come back once each.
**So two detectors agreeing exactly is what is fatal, and only a noiseless picture makes
them agree exactly.** That is worth carrying as a general lesson about this whole
programme: a rendering is not a weaker capture, it is a picture with the disagreement taken
out, and every arbitration tuned on disagreement is a candidate to behave differently under
one. The fix belongs in `occupancy.py` -- agreement should reinforce a reading rather than
annihilate it -- and it is a third bug PR this item has now surfaced without taking, beside
`SceneToSearch.expected_pieces`.

Both expected-to-fail marks stay strict and name the arbitration instead of the sizes.

#### The CI failure, and why nothing in the process could have fixed it

`test_montessori_simulated_camera.py` failed CI on `mujoco.FatalError: gladLoadGL`, two
failures and six errors, and the reason was written in the workflow that failed it: MuJoCo
reads `MUJOCO_GL` when Python first imports it and holds to what it read. `ci_reusable.yml`
exported `egl` for `semantic_digital_twin` only, whose video recorder was the one thing
that rendered offscreen; the simulated camera is the second and runs in the `experiments`
job. Reproduced in a container with no display -- the same two failures, six errors and
GLFW warnings -- and `MUJOCO_GL=egl` takes the file to 12 passed and 2 xfailed.

The corollary is worth recording because it is `main`'s and will outlive this branch:
`select_offscreen_rendering_backend()` **cannot reach either of its callers**. Both
`MujocoVideoRecorder.start` and `SimulatedCamera.start` call it after their module has
imported mujoco, so it sets a variable that is already too late to matter; the four lines
had the same shape inline on `main` before they were extracted. Only the environment a run
is started from can choose the backend. The function keeps its behaviour and gains the
warning that says so.

The job's other 9 failures and 14 errors were the base branch's duplicate `RecordedLook`,
which the base has since merged the fix for; this branch takes the base's merge, cleanly,
and they go with it.

**Verified**, Python 3.12 session container with `MUJOCO_GL=egl`:
`test_montessori_simulated_camera.py` 12 passed and 2 xfailed, `test_montessori_world.py`
25 passed and 1 skipped, `test_region_appearance.py` 4 passed,
`test_mujoco_rendering_backend.py` 4 passed. The whole of `test/experiments_test` this
container collects runs 707 passed, 4 failed, 1 skipped, 6 xfailed, and all four failures
reproduce identically on the branch's own merge commit in a worktree -- the
`test_free_space_volume_estimation` one, the two `test_montessori_perception_backend`
narrowing ones, and `test_montessori_insertion_diagnosis`'s `failed_motions` keyword, which
arrived with the base's merge of `main` and which #265's own session has already recorded.

### `montessori-scenarios` (#296): the second review round, 2026-09-08

Two threads on `experiments/montessori/scenarios.py`, taken in `66eefdbb9`. Both are
about the same thing from two sides: *what a run does to its scene* and *what a goal
reads off it* were both being written by hand instead of being asked of the twin.

**The goals now ask the twin's predicates.** `ThePieceIsInItsHole` measured a distance
and a height; it now reads `InsideOf(piece, landing_region_for(piece)) >= 0.9`. That is
not a choice of ours twice over: `MontessoriWorld` already builds a landing region per
hole, documented as "the `Region` a shape is checked for containment against once it has
fallen through the hole" and sized so a shape resting on the board never registers; and
segmind's `BaseContainmentDetector` already reads a containment as
`InsideOf(obj, body).compute_containment_ratio() > 0.9`, with #265's `event_monitoring.py`
registering exactly those regions as its extra candidates. Measured on a cube dropped over
the square hole: `0.0` on the table, `0.0` while carried above the hole, `1.0` once
through. Against the board's own body the same run reads `0.5`, which is why the region
rather than the board is the container, and a test pins that choice.
`ThePieceIsHeld` now asks `robot_holds_body`, so the fingers have to be around the piece.

**A run is carried in MuJoCo, and `hang` is gone.** A scenario builds its world and hands
it to a `SimulatedScene`, which mirrors it into MuJoCo and advances it by a stated stretch
of simulated time — stepped from the scenario, not from a thread of the simulator's own,
so a run is reproducible. Three of the four actions are now the physics doing it: settling
is gravity (a piece stood 100 mm up returns to exactly its resting height), the push is an
actual pusher on a rail sliding into the piece (the prism travels from `y = −0.328` to
`y = −0.293` and ends against the pusher), and the insertion is the fall. Picking up takes
the robot to the piece: the gripper is aimed by the midpoint of its finger tips, opened,
driven there by `compute_inverse_kinematics`, and closed, and the piece has not moved when
it is held.

**Where the physics stops, and why it is a call rather than an omission.** Carrying a held
piece is still scripted. Two measurements say why, and they belong to whoever picks the
question up: a grasp held by *position-driven* fingers does not survive being simulated —
MuJoCo resolves the penetration by ejecting the piece, and in a bare two-finger rig a cube
at `z = 0.015` is squeezed to `0.031` and left behind on the lift; with *position
actuators* on the same rig (`kp = 10000`, ±100 N) the same grasp rides from `0.015` to
`0.183`. So a friction grasp needs the robot's joints actuated in the twin. The pieces for
that exist — `Actuator` plus `MujocoActuator` express a MuJoCo position servo — but nothing
in the workspace actuates the Montessori robot, and `MujocoSimulator` has no
`set_actuator_value` to command one with; it has getters only. That reads like the
robot/world setup's job or the demo's rather than a scenario module's, and the thread is
left open asking the developer where it should live.

**Two findings for whoever builds it.** Re-parenting a body while the simulation runs does
not reach MuJoCo at all — the model was compiled with the piece on a free joint, so the
twin says the piece hangs from the gripper while the simulation still has it on the table.
(Coraplex's own `PickUpAction` re-attaches *after* physically closing the gripper, with
`ReAttachNode`; that is fine as bookkeeping and cannot be the grasp.) And without actuators
the arm sags under gravity in simulation.

**The #265 question, answered the same way as the base-branch one.** The thread asked
whether #265 was needed for any of this. Measured:
`git grep -l 'MujocoSim\|start_simulation' origin/claude/icra-experiments-simulation-pipeline-w4ep7n -- experiments/`
returns nothing, so #265 drives no simulation either; everything the physics needs is on
`main`. What #265 carries that is relevant is only the landing regions' wiring into
segmind's detector, which a goal asking `InsideOf` directly does not need.

**The test dataset gains a two-fingered robot.** `SyntheticFixedArmRobot` has one revolute
joint and no geometry, so it can neither reach the table nor give a ray-casting predicate
finger tips to cast between. `SyntheticGraspingRobot` is a gantry arm with a pincer, from a
URDF in the repository; the Montessori scenario tests bind it instead.

**Standing hazard corrected, and this time for the whole suite.** "Nothing on these
branches runs in a session container" is now wrong even for `pytest`. A Python 3.12 virtual
environment with `mujoco`, `casadi~=3.7.0`, opencv, `scikit-image`, `piqp`, `transforms3d`,
`trimesh`, `rustworkx` and the `random_events`/`probabilistic_model` wheels, plus stubs for
`xacro` and the compiled `giskardpy_bullet_bindings` and `libegl-mesa0` for offscreen
rendering, generates all five ORM interfaces and runs `test/experiments_test` — 380 passed,
MuJoCo simulation included. The two failures left are ones `main` fails there too (a
missing `vhacdx`, and a robot-spawn test). The compiled Bullet bindings remain the one
thing that will not build. Note the interpreter: coraplex uses `type X[T] = ...`, so 3.12
is required to import it at all.

**Left open.** The `Goal`-as-`Predicate` thread from the first round is still open, waiting
on whether that change should have landed on #261 instead; the physics thread above is open
on the actuation question.

## 2026-09-08, later still: main merged into #265, and #292 folded in

The two things left outstanding on #265 at the end of the narrowing round are both
closed, and the branch's CI is now down to what those two changes carry.

**main met the branch in exactly the four files this roadmap predicted**, and each side
had brought something the other needs, so all four resolutions keep both:

| file | what met | resolution |
|---|---|---|
| `world.py` | `memoize` moved to `krrood.patterns.caching`; the branch added a `BeliefSource` import beside the old spelling | both, at the new location |
| `mapped_variable.py` | `CallVariable._update_type_` rewritten on both sides, for different cases | reads a method off its owner class when the child resolves to no type, keeps the branch's reading of a `__call__` class otherwise |
| `geometry.py` | main gave `Color` `to_hex`/`from_hex` and `__hash__`; the branch gave it `ColorName` and a verbalization | both; main's `RED`/`PINK` classmethods dropped as the branch's already answer with those colours |
| `test_color.py` | two files of one name testing different things | one file of two sections |

The `memoize` hazard this roadmap warned of was real and would have been silent: left as
git merged it, `world.py` imports a name from a module that no longer defines it.

**And one collision git could not flag, which is #192's shape a fourth time.** main's own
new `test_relational_circuit_registry_causal.py` reaches a query's variable as
`query.variable`. Since #192 that builds an attribute expression for a field called
"variable" rather than raising, so what actually fails is `random_events` asking
`issubclass` of the `None` type it resolves to, four tests deep and in another package.
It is worth stating as a standing hazard rather than an incident: **every branch main
merges into this one from here on can carry a new reader of a name #192 retired, and
none of them will fail where they are written.** The convergence's own technique - make
`Match._is_own_name_` refuse the retired spellings, run the suites, migrate every hit -
is the way to find them, and is cheap enough to repeat on each merge of main.

**#292 is merged into the branch**, so the duplicate `RecordedLook`, the 12 mm hole
displacement and the requoted narrowing millimetres are all here, and #292 is closed as
merged. Its two root causes are recorded in the item's own notes and in the section
above.

**What the numbers say.** Thirteen of fifteen CI jobs were green on the main merge alone
(`93cdd21c9`), and the two that were not are precisely `krrood` (those four causal tests)
and `experiments` (the duplicate `RecordedLook`) - the two the commits above fix. In a
session container, with `--orm-build=never`: `test/krrood_test` 3014 passed and 2 failed,
both `test_object_diagram`, which needs graphviz's `dot`;
`test/semantic_digital_twin_test` the same 45 failures as the pre-merge branch, with its
45 added errors also present on plain `main` for a missing `iai_apartment`;
`test/experiments_test` 684 passed with 18 failures, every one a missing ROS package or
database and every one identical before the merge.

**The container note is now stronger than either of the earlier corrections.** `pytest`
is not blocked here at all: `--orm-build=never` (equivalently `CRAM_ORM_BUILD=never`)
skips the conftest's generation, and with `pyjpt`, `matplotlib`, `flask` and `mypy`
installed beside the workspace the whole of `test/krrood_test`,
`test/semantic_digital_twin_test` and `test/experiments_test` run. What still needs CI is
the ORM generation itself and anything importing ROS - `test/coraplex_test`,
`test/giskardpy_test` and `test/segmind_test` among them.
## 2026-09-08 (last): the merge's second silent rename, and the hazard restated

The main merge left `krrood` green but `experiments` red on one test, and the cause is
the same shape as `query.variable` rather than anything the four resolved files carried.
main's `2664659b4` renamed `MotionDidNotFinish.failed_motions` to `unfinished_motions`
and followed both readers it could see -- `executables.py` and `test_exceptions.py`,
each of which passes the field *positionally*, so neither line had to change. The reader
it could not see is this branch's own `test_montessori_insertion_diagnosis.py`, which
names the field by keyword and exists on no ancestor of that commit. Two sides, two
different files, no conflict, and a `TypeError` eight minutes into a CI job.

Migrated in `06e7af3eb`. What the test asserts -- that a motion failure is an
informative plan failure, so the diagnosis reads `PLAN_FAILED` -- is untouched; only the
field follows the rename, which is what AGENTS.md means by a rename being finished when
every reader reads the new name, and is the same justification `7a6f8f7a9` was taken
under.

**So the standing hazard is restated, and it is now wider than #192.** It was recorded
as "every branch main merges into this one from here on can carry a new reader of a name
#192 retired". That is a special case. The general form: **every merge of main can carry
a rename whose only stale reader sits in a file main never touched, so git reports no
conflict and the failure surfaces nowhere near where it is written** -- for #192 in
another package entirely, here eight minutes into a job. Three instances now: #159's
readers at the convergence, `query.variable` at the main merge, `failed_motions` here.

The cheap sweep to repeat on each merge of main, which found no fourth instance this
time: diff the fields main removed and did not re-add over the merge base
(`git diff $(git merge-base <merge>^1 <merge>^2)..<merge>^2` filtered to dataclass field
lines), then grep the tree for a surviving reader of each. Eleven names came out;
`failed_motions` was the only one with a reader left, the rest being either lines that
merely moved within main's own source or names nothing reads. For a retired *method* or
attribute on a class that delegates unknown names -- `Match` -- that grep is not enough
and the `_is_own_name_` guard trick is still what finds them.

**Measured.** On `0e0bacfad`, twenty-two of the twenty-three checks passed and this was
the single failure; `krrood` was green, which is `7a6f8f7a9` confirmed. Locally the file
runs 14 passed. The full `test/experiments_test` in a session container is no longer the
clean comparison the earlier entries record -- the generated ORM interfaces are absent
from this container now, so `psycopg`, `rclpy`, `rosbag2_py`, `rtree` and `vhacdx` gaps
account for 25 failures and 11 errors, every one of them an import of something missing
and none of them a defect. CI, which has all of it, is the authority and reported exactly
one failure. CI on `06e7af3eb` had not reported when this was written, and per the
standing rule no check of it was armed.

### `montessori-scenarios` (#296): the third review round, 2026-09-08

Five threads, all on `scenarios.py`, taken in `db746a949`. Three resolved, two left open
because the reply asks rather than answers.

**The robot is commanded by coraplex, and it runs headless.** Every hand-written gripper
method is gone; `SortingScene.pick_the_piece_up` is `PickUpAction` and
`put_the_piece_down_at` is `PlaceAction`, performed under `simulated_robot` so giskard
compiles and ticks the motion statechart. The surprise worth carrying is that this needs
no ROS at all: `Ros2Executor` takes `Context.ros_node = None`, and a pick-and-place is
1.4 s in a session container. Conditions are switched off for a scripted run
(`context.evaluate_conditions = False`) -- a coraplex precondition is about a robot that
perceives and navigates, while a scripted scene states its preconditions as its layout.

**A simulation is compiled against one kinematic model and cannot follow a change to it.**
`PickUpAction` ends in a `ReAttachNode`, and a live MuJoCo mirror answers that re-parent
with `free joint can only be used on top level`: the piece is still on its
`Connection6DoF`, now below the gripper. So `SimulatedScene` builds its mirror on demand
and `stop()` drops it; a step that commands the robot lets go first and the next stretch
of physics mirrors the world as it then is. This is the general shape rather than an
incident -- anything that re-parents a body has to be outside the simulation's lifetime,
and `world.move_branch` keeps the body's own connection type, which is what makes the
mirror refuse it.

**The space under a hole is measured rather than stated.** The comment was "I don't like
that we get the hole region by its name, this should use something like the GCS and
bounding boxes to get the free space under the holes", and both halves are now true.
`MontessoriWorld` builds each landing region from
`VolumetricGraphOfBoundingBoxes.free_space_from_bounding_boxes` over the column the hole's
own footprint cuts down to the table, with the board's and drawers' collision boxes
subtracted (`build_bloated_obstacle_collection`, z clearance zero so the shaft is not
shortened). It is measurable only because `_board_body` and `_drawer_body` already build
their collision as a grid of boxes with the shafts left open. `LANDING_REGION_XY_MARGIN`
(0.03) and `LANDING_REGION_TOP_CLEARANCE` (0.02) are deleted with it; only
`LANDING_REGION_BOTTOM_MARGIN` survives, and its docstring already said why it is not a
fudge -- a piece resting on the table has its lowest vertices exactly in the table's
plane. The regions are now the openings themselves: square 32 x 32 mm, rectangular 22 x
42, triangle 36 x 42, disk 5 x 48 (it is a slot, not a coin-shaped opening), each 85.5 mm
tall. `ShapeSortingHole` carries its own `landing_region`, so the name is spelled once.

**Two findings about grasping in this workspace**, both measured, both worth knowing
wherever a grasp is checked next:

- A tool frame is the point between the fingertips, not the palm. The mimic pincer had
  `tool_frame = pincer_link`, so an action that takes the tool frame to a piece put the
  fingertips 30 mm below it and the grasp closed on air.
- `bodies_in_gripper` samples points on the two fingertip meshes and casts rays between
  them, and a ray starting on a fingertip's own surface mostly hits that fingertip first
  -- so `robot_holds_body` reads reliably only when the fingertips *interpenetrate* the
  body. On a grasp whose fingers surrounded a 22.4 mm piece with 3.8 mm clear on each
  side, 1 read in 10 found it; with the fingers shut into the piece, 10 in 10. A
  `JointPositionList` also stops within its own tolerance (about 10 mm per joint here) of
  the position it was given, so a gripper's `CLOSE` state has to ask for more travel than
  a touching pose if the predicate is to read at all.

**Left open, both the developer's.** Whether `InsideOf.minimum_containment_ratio` -- which
exists on #265 and not on this base -- should be ported here now, taking a conflict with
#265's own rewrite of `predicates.py`, or waited for. And whether `PlaceAction` should
gain an optional `grasp_description`: it works out where to take the gripper from the
grasp description of the pick it finds *in the same plan*, and falls back to
`FRONT`/`NoAlignment` when there is none, so a place performed as its own scripted step
always takes the fallback while the piece is held by a `FRONT`/`TOP` grasp. It happens not
to matter on this board -- the piece lands at the hole's own x and y either way -- but
that is luck rather than design. The alternative is `PickAndPlaceAction`, which puts both
in one plan and works here too, at the cost of collapsing the run's two scripted steps
into one.

### `montessori-scenarios` (#296): the fourth review round, 2026-09-08

Two threads and one review comment. The review comment — *generate MuJoCo videos of the
tests, use the video/recording tool we have for MuJoCo in this repository* — is the one
the third round missed: it is a review's own body rather than a comment on a line, so it
never appeared among the pull request's review threads. Worth carrying as a process
note: a round is not read until the reviews themselves are read, not only their threads.

**A run is filmed with `MujocoVideoRecorder`, in takes.** A scenario built with
`filmed=True` carries a `SceneRecording`; the takes are written out as one video, into
`$MONTESSORI_SCENARIO_VIDEO_DIRECTORY` or a directory of its own beside the machine's
other temporary files. It has to be takes rather than one stretch for the reason this
branch keeps meeting: a simulation is compiled against one kinematic model, and a grasp
re-parents the piece. So `SimulatedScene` now lets go of what carries it whenever the
world's *model* changes — a sibling `ModelChangeCallback` — rather than each
robot-commanding step remembering to let go first, and the recording is cut and taken up
again at the same moments.

**The film is made from the simulation carrying the run**, not a second one beside it, so
filming cannot change what it films: a filmed and an unfilmed sorting run leave the cube
at the same place to the last digit, and a test pins it. It costs 11 s against 2.6 s, all
of it rendering (about 100 ms a frame in software, and near enough independent of
resolution — 115 ms at 640 × 480 against 96 ms at 320 × 240 — so the only lever is fewer
frames). The video is 15 frames a second, with a motion filmed every third change to the
world, since a motion has no simulated clock to be paced against.

**What no video can show is the carrying**, and that is a finding rather than an
omission. While the robot holds the piece the world cannot be exported to MuJoCo at all:
`ReAttachNode` goes through `world.move_branch`, which keeps the moved body's own
connection type, so the piece's `Connection6DoF` ends up under the gripper and the model
is refused — *free joint can only be used on top level*.
`World.move_branch_with_fixed_connection` is the alternative and a held body being fixed
to the hand is the truer statement, but which connection an attach makes is coraplex's
decision, so it is asked rather than taken.

**Three mechanical findings, all measured, none of them this item's to fix:**

- **Building a MuJoCo mirror is itself a change to the world's model** — `build_world`
  opens a `modify_world` block to put the world under a root of the simulation's own — so
  anything that reacts to a model change by dropping its mirror has to be deaf while it
  builds one.
- **A change already under way reaches every callback the world had when it began**
  (`update_model_version_and_notify_callbacks` iterates a copy), so a simulation being let
  go of mid-notification has to be *paused* as well as stopped, or its spawner still runs
  against the model it can no longer follow.
- **A callback that stops itself can unregister another one.** Every `Callback` is a
  `WorldEntityWithClassBasedID`, so all instances of one class share an id and compare
  equal, and `StateChangeCallback.stop`'s `remove(self)` takes whichever instance was
  registered *first*. Two MuJoCo mirrors of one world — a recorder beside a simulation —
  therefore break each other on stop, and the next state change raises `AttributeError:
  'NoneType' object has no attribute 'previous_world_state_data'` inside
  `MultiSimSynchronizer._on_state_change`. A one-line fix in `semantic_digital_twin`
  (remove by identity), so it belongs in a bug pull request of its own; the design here
  avoids it by never having two mirrors at once.

**`PlaceAction` gained an optional `grasp_description`**, the developer having answered
the third round's question with *do (1)*. One kw-only field defaulting to none, and
today's search-then-fallback is what it falls back to, so no existing caller changes.
Measured on this board: told the `FRONT`/`TOP` grasp the piece is actually held by,
all three poses the place takes the tool frame to change by a rotation. Two tests in
`test_graph_parsing.py` state it against the definition rather than against a pose — told
plans like found, and told wins over the pick-up before it — and, like the rest of
`test/coraplex_test`, they are CI's to run.

**Where the demo's actuation should live is still the developer's**, and the answer now
has the measurements it needed. Everything that makes `montessori_demo_mujoco.py` work —
`equipment.py`'s servos and gravity compensation, `real_time_simulation.py`'s `command`,
the `PickUpActionMujoco`/`PlaceActionMujoco` pair, `grasp_contact.py`, and
`MujocoSimulator.set_actuator_control` — is about 1,200 lines living on `tracy_icra` and
on no ancestor of this branch (`git ls-tree origin/main -- .../tracy_experiments/` is
empty). And that pair deliberately does *not* use coraplex's actions: its own docstring
records that a Giskard closed loop ticking live against the world races
`MujocoSynchronizer`'s physics-thread sync, so it plans against a scratch copy and plays
trajectories back through actuators, holding by friction and never attaching. That is the
opposite of what the third round asked for and got. The scenarios themselves are already
the demo's — generic in their robot, with the `Tracy…` bindings in the module — and the
one seam still closed is that `MontessoriSortingScenario` builds its own
`MontessoriWorld` rather than being handed the demo's `TracyMontessoriWorld`, which is
not on this base either. Three ways forward are on the thread; none was taken unasked.

### The third review round on #298, 2026-09-08: a hole is measured rather than seen, and agreement stops annihilating

Two comments, both on the two expected-to-fail marks: *"you can generate a depth image
in mujoco right? see the best way of doing that, which gets you the holes using depth.
Also for the detectors agreeeing on both then dropping, we need to find a solution for
that"*, and *"we need to find a solution for this issue"*. Both marks are gone: the
item's own criterion passes, and so does the rung below it.

#### The depth was already rendered; nothing read it

`SimulatedCamera` has answered with depth since its first commit -- what a look did with
it was measure how tall a piece stands, and nothing else. Three pieces were missing:

- `RgbdFrame.measured_height` -- how high the surface seen at each pixel stands, in the
  frame poses are reported in, NaN where the sensor returned nothing.
- `Orthophoto.measured_height`, laid over a plane by the same warp as the colour and read
  at the nearest pixel rather than averaged (a reading either side of a rim is the lid or
  the floor of the hole, and their mean is neither), and `opening_mask(drop)`, the pixels
  the camera measured a surface at least that far below the plane.
- `BoardDetector` reads its openings from darkness **or** from depth, each sized on its
  own before the two are put together. That last is not tidiness: Otsu always splits a
  surface in two whether or not anything is cut through it, and a plane stated above the
  surface actually lying in it is measured below along the whole of that surface -- one
  gap the size of the surface, which is an opening in nothing. Either left whole swallows
  what the other found, and on the shipped captures the second one would have swallowed
  the board.

**A hole is ten millimetres deep, not eighty.** The second round's note that the twin's
holes are "cut through an 80 mm blank" is wrong about what a camera sees: the mesh is cut
clean through, but the drawers sit directly under the lid (`_DRAWER_POSITIONS` at
z=0.553, `DRAWER_SCALE.z` 0.06, so their tops stand at 0.583 against a lid at 0.593), so
a look down a hole measures the drawer ten millimetres below. `minimum_hole_depth` is
half of that. It is also why the first round's *"a look shows no opening for the board to
be found by"* was only half right -- there is no opening in the *colours*, and there is a
plain one in the depth.

#### The seed was never the problem; the fit was

With the openings read from depth the seed landed at (-0.401, 0.0013) against the twin's
own (-0.400, 0.000) -- and the fit then turned the layout **ten degrees** off and moved
it 17 mm, because a rendered hole's walls are lit like the lid and the layout had nothing
in the picture to grip. So a rim is now an edge: `EdgeDistances.of(orthophoto,
together_with=...)`, given the rims of the openings the colours do *not* carry (a rim
that is dark on one side is already an edge the picture holds, and drawing a second one
over it would weigh that rim against the rest of the picture differently).

| the layout fitted to | centre | turn | each hole against the one the twin cut |
|---|---|---|---|
| the colours alone | (-0.417, -0.002) | -10.0 deg | worst 32.0 mm, median 14.9 mm, and the cube's hole matched to a cylinder's |
| the colours and the rims | (-0.400, -0.001) | 0.0 deg | worst 5.4 mm, median 1.2 mm, every hole on its own category |

**The captures cannot change, and that is measured rather than argued**: on all six, the
depth contributes *zero* hole-sized openings, so the openings are the same dark patches as
before and the rims are empty. `test_montessori_detection_on_captures.py` runs 57 passed
and 4 xfailed, as it did.

#### What the captures' own depth says, which is worth the developer's eye

Reading it was the first time anything in this package had. It does not resolve a hole,
and it disagrees with the rig the setup states:

- The board's top surface measures at **0.879**, where `recorded_setup` states its lid at
  **0.960** -- 81 mm out, and the table's own stated 0.880 is measured correctly at 0.879.
- A piece resting on the lid measures 0.896 and a piece on the table 0.895. If the lid
  stood 80 mm above the table those two would differ by 80 mm.
- Inside a hole's own outline, 40 to 85 per cent of pixels carry no reading at all, and
  what is measured lies within 12 mm of the board's own surface -- sometimes above it.
- A bare patch of table scatters 14 mm from end to end.

So either `LID_HEIGHT` and `TABLE_HEIGHT` or the captures' depth extrinsics are wrong,
and `pipeline.py`'s own module docstring -- *centimetre-scale noise, far too coarse to
measure a thirty millimetre piece* -- is if anything generous. Not touched here: the
board is found on all six captures by its darkness, and moving a stated plane moves every
rectification in the package.

#### Occupancy: two defects, and the second is the larger

The first is the one the round two note named: `keep_one_detection_per_place` drops both
readings of a place unless one leads, so two ways of looking that agree annihilate. Now
only a reading that names *something else* can take a place from its holder -- two
readings that name the same thing are that thing read twice, and there is nothing there
for a lead to settle.

The second was under it and is worse. `OccupiedVolume.shared_area` measures in metres,
and OpenCV's convex intersection holds to a tolerance of its own: it answers zero once
the step from one outline point to the next falls below about four thousandths of a unit.
Measured over regular polygons of a 14 mm radius offset by one millimetre, in metres: a
16-gon intersects, a 24-gon answers zero, a 64-gon -- which is what a rectified cylinder's
outline is -- answers zero. So **two readings of one cylinder a millimetre apart were
measured to share no ground at all**, and both were reported. Squares of 40 mm sides were
never affected, which is why every test in `test_montessori_occupancy.py` passed: they are
all built out of squares. The outlines are now intersected in millimetres.

One existing test stated the rule the developer asked to change, so it is restated rather
than deleted: `test_neither_of_two_readings_of_one_place_is_reported_where_neither_leads`
built both readings as cubes, and now builds one cube and one cylinder, since disagreement
is the case it means. Two tests are added beside it -- that two readings naming one thing
report it once, and that two readings of one rounded thing a millimetre apart are read as
one place.

**Measured on the reference scene**, one of each piece perception knows on the table: all
four reported once each with their own categories, each within a millimetre of where the
twin put it, and the board found with its six holes. The same numbers with the regions
drawn see-through, so the reading no longer depends on the markers at all.

**Verified**: `test_montessori_simulated_camera.py` 15 passed (was 12 passed, 2 xfailed),
`test_montessori_detection_on_captures.py` 57 passed and 4 xfailed, unchanged,
`test_montessori_occupancy.py` 24 passed, `test_montessori_views.py` 31 passed,
`test_montessori_explanations.py` 17 passed.

### The fourth review round on #298, 2026-09-09: what it asks for is a plan, not a round

The branch is finished as an item and stalled as a conversation. All 23 checks pass on
`15dfd354cd`, `mergeable_state` is clean, the item's own criterion passes and both
expected-to-fail marks came off in the third round. What holds it is two threads opened
on `pipeline.py` after those replies, neither of them a defect, and the last comment on
the second says in as many words: *"Maybe all these can be organized as plan items,
Discuss with me the best course of action regarding that"*. So the round is answered by
a proposal put to the developer rather than by a push, and this section records what was
found rather than what was resolved.

**What the two threads actually ask for.** `r3965517956` asks whether holes would be
better found from depth and whether a second, depth-dependent hole detector should stand
beside `BoardDetector`. It reads as unanswered but is half answered already: the third
round made `BoardDetector` read its openings from darkness *or* from depth, each sized on
its own. What is not answered is the *beside* -- a detector of its own rather than a
second reading inside one, which is the same question the sibling thread asks in general
form. `r3965555439` and its three replies are that general form, and they are one ask in
four steps: the five stated defaults on `BoardDetector` (`hole_size`,
`minimum_hole_count`, `minimum_hole_depth`, `minimum_lid_area`, `seed_reach`) should be
derived from what the twin already knows about the board rather than written down; the
concepts under them -- counting a feature on a perceived body, a hole, the area of a
surface that may have holes -- should be raised to a meta level as predicate classes or
as a hole/perforated-surface detector family with capabilities; a detector's capability
should name the *fields of classes* it can answer, spelled as EQL `Attribute`s or
`MappedVariable`s rather than as field-name strings; and a look should then be asked for
by handing the backend an underspecified EQL `Match`, which helpers fill out from what
the model knows about the named class, possibly as an EQL-based RDR. The same description,
verbalized, is what a VLM or VQA would be asked.

**Why none of it is this branch's.** Only the first step is even arguably a round on
`pipeline.py`, and the developer bundled it with the rest deliberately -- deriving the
five defaults from the board is the small case of the general mechanism, and taking it
alone would build a Montessori-shaped answer to a question asked at the meta level. The
remaining three steps are `icra-mechanism`'s territory as the plans already stand:
`backends-declare-their-capabilities` is where a capability is declared, and
`perception-backends-are-interchangeable` is where a VLM answers a look behind the same
interface. So what the round needs is items, and which plan they belong to is the
developer's call.

**The branching change is the larger half, and it is the plan's rather than this item's.**
The same comment states: *"I want first to merge everything now fast into 265 and then
into tracy_icra then merge any new features into tracy_icra directly and stop basing them
on main or on other tracks. Because I want to start recording episodes with perturbations
in the simulation as fast as possible."* That reverses the base every in-flight item in
all three ICRA plans was cut under, and it retires the readiness rule those cuts were
argued from -- an open, non-draft pull request counting as ready to build on is what
#278, #294 and this item were each cut under, and `montessori-scenarios` (#296) argued
*against* #265 as a base on measured grounds only yesterday. Under the new direction that
argument stops applying, because the sideways-merge cost it turned on is paid once by the
fast merge into #265 rather than by each branch. It is recorded and asked, not applied.

**One dependency reading changed while this sat.** `integrated-simulation-pipeline` (#265)
is a draft again, so `check_dependency_readiness.py` reports `is_ready: false` for it
where "open and not a draft" is what this item's cut off #265 was argued from. Nothing
already built on it is affected, and the developer's own merge-everything-into-#265 plan
is the likely reason it is a draft; noted because the same reading is what three other
items were cut under and a later run should not read the regression as new information.

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

### `montessori-scenarios` (#296): the fifth review round, 2026-09-09

One thread, and the answer to the question the fourth round left with the developer:
*where should the demo's actuation live, and how do the scenarios reach the demo?* —
**do (1)**. Option (1) was to open the one seam that was still closed and leave
`tracy_icra`'s actuation where it lives, so that
`tracy-demo-takes-the-integrated-branch` is where the demo's world, its actuators and
these scenarios meet.

**A scenario is built on the scene it is given.** `MontessoriSortingScenario` no longer
constructs a `MontessoriWorld`: it is handed a `MontessoriWorldBuilder` and asks it for
a fresh scene per trial. `BoardOnItsOwnTable` is this package's own — the board on the
table `MontessoriWorld` stands it on — and a demo's is a second implementation rather
than an edit here.

**Where the robot is bolted moved with it**, onto `BoardOnItsOwnTable`, and that is the
part worth recording, because it is what makes the seam usable rather than nominal.
Mounting is not separable from building the scene in the demo's case: `parse_tracy`
strips the actuators an already-parsed robot cannot be merged with,
`tracy_table_mount_position` reads both the mount and the table height off that parsed
world, and `TracyMontessoriWorld` needs the table height to place the board at all. A
seam that let a demo choose the world but kept the parse and the mount here would have
left the demo unable to use it.

**And the table a piece rests on is the given scene's**, not the module's constant:
`MontessoriWorldBuilder` states its own `table_top_z`, `resting_height_of` moves onto it
from a free function, and the pusher's rail reads it too. Left as it was, a scene whose
table stood elsewhere would have had its pieces placed at this table's height and its
pusher sliding at that height as well.

**What is still this table's**, and is named rather than built: `LayoutArea` and
`PiecePlacement.standing_height` measure against the module's `TABLE_TOP_Z`, so a scene
on another table also needs its layout stated in that frame. It is a layout's own frame
rather than the scene's, the demo does not need it to run a scenario, and inventing it
now would be a second guess at what a demo's layout wants.

51 tests in the module. The three new ones were written first and each was checked by
mutation: building a `MontessoriWorld` inline again fails the one that says the run
happens in the scene the builder built, reading the resting height off `TABLE_TOP_Z`
again fails the one that says a piece stands on the given scene's table, and bolting the
robot at a fixed position fails the one that says the scene decides where it stands.

### `integrated-simulation-pipeline` (#265): the fast convergence, 2026-09-09

Applying the developer's direction from #298's fourth round (*"merge everything now fast
into 265 and then into tracy_icra"*, see the entry above): every in-flight branch across
`icra-foundation` and `icra-evidence` that still had one is now merged into this branch,
each at its own tip and never sideways, matching the 2026-09-06 convergence's own rule.

Nine merges, in dependency order: `simulated-camera-feeds-perception` (#298),
`scenario-domain-model` (#261), `run-results-recorded-into-sql` (#262),
`episodes-recorded-through-ormatic` (#271), `episodes-queried-by-eql` (#278),
`episode-artifacts-recorded` (#294), `montessori-scenarios` (#296),
`question-set-and-ground-truth` (#295), `paper-figures-from-episodes` (#297). Each is
recorded on its own item below.

Every merge but three was conflict-free. The three that conflicted were each resolved by
keeping both sides rather than picking one - `generate_orm.py`'s `ignored_classes`
additions are independent per branch and compose by concatenation, and the same was true
of `ci_reusable.yml`'s EGL-offscreen comment (rewritten once to name all three MuJoCo
offscreen renderers instead of choosing one branch's wording) and `placing.py`'s typing
import. The one substantive conflict was `segmind/datastructures/events.py`:
`question-set-and-ground-truth` (#295) introduces `AgentInteractionEvent` as a marker for
"the agent acted on the tracked object", and this branch already carries
`EventWithEffect`/`ComesToRestEvent` on `PickUpEvent`/`PlacingEvent`/`InsertionEvent` for
the physics effect each one causes - taking either side whole would have dropped one of
the two. `AgentInteractionEvent` declares no fields of its own, so each event class now
inherits both bases; verified in isolation with an equivalent class hierarchy that the
MRO composes cleanly and `effect()` and `isinstance(event, AgentInteractionEvent)` both
hold for all three.

Every changed and merged file was byte-compiled; no stale reader of a retired module
(`montessori.results_recording`, `montessori.sorting_results`, both replaced by
`episodes.episode`/`episodes.recording` in #271) was found by grep. CI has not yet run on
this session's tip - the full workspace needs ROS and cannot be collected in this
container - so this is not verified the way #292 and the main-merge above were: it is
compile-clean and conflict-resolution-reasoned, not CI-green.

Left for the developer, per the same comment's direction: merging this branch into
`tracy_icra` and running the demo on the UR10 is `tracy-demo-takes-the-integrated-branch`,
a separate item that names the robot as a dependency this session does not have. Nothing
here does that merge or starts new work off `tracy_icra`.

### `simulated-camera-feeds-perception` (#298): merged into #265, 2026-09-09

Merged whole into `integrated-simulation-pipeline` (#265) as the fourth review round
concluded it was ready to: all 23 checks green on `15dfd354cd`, `mergeable_state` clean,
the item's own criterion passing. No conflicts. See `integrated-simulation-pipeline`'s own
entry above for the session-wide convergence this was the first step of. The branch's own
open questions from that round - the depth-dependent hole detector and the meta-level
capability description - are not this item's; they are `icra-mechanism`'s, per that
round's own conclusion.

### `scenario-domain-model` (#261): merged into #265, 2026-09-09

Merged into `integrated-simulation-pipeline` (#265). One conflict in `generate_orm.py`,
purely additive (this branch's scenario-model `ignored_classes` loop beside #298's
simulated-camera one already on the branch) - resolved by keeping both. See
`integrated-simulation-pipeline`'s entry above.

### `run-results-recorded-into-sql` (#262): merged into #265, 2026-09-09

Merged into `integrated-simulation-pipeline` (#265), conflict-free. Its bulk
(`results_recording.py`, `sorting_results.py`) was already on the trunk through earlier
merges; what this brought was the `ResultsDatabase` naming fix (the board rather than the
robot) made since. See `integrated-simulation-pipeline`'s entry above.

### `episodes-recorded-through-ormatic` (#271): merged into #265, 2026-09-09

Merged into `integrated-simulation-pipeline` (#265), conflict-free. Retires
`montessori/results_recording.py` and `montessori/sorting_results.py` in favour of the one
`Episode` model (`episodes/episode.py`, `episodes/recording.py`); grep confirms no reader
of either retired module survives on the merged tree. See
`integrated-simulation-pipeline`'s entry above.

### `episodes-queried-by-eql` (#278): merged into #265, 2026-09-09

Merged into `integrated-simulation-pipeline` (#265), conflict-free. See
`integrated-simulation-pipeline`'s entry above.

### `episode-artifacts-recorded` (#294): merged into #265, 2026-09-09

Merged into `integrated-simulation-pipeline` (#265), conflict-free, purely additive
(`episodes/artifacts.py`). See `integrated-simulation-pipeline`'s entry above.

### `montessori-scenarios` (#296): merged into #265, 2026-09-09

Merged into `integrated-simulation-pipeline` (#265). Two conflicts, both purely additive
and resolved by keeping both sides: `ci_reusable.yml`'s EGL-offscreen comment (rewritten to
name all three MuJoCo offscreen renderers rather than choosing one branch's wording) and
`generate_orm.py`'s `ignored_classes` list. See `integrated-simulation-pipeline`'s entry
above.

## 2026-09-09, later: `tracy_icra` merged in, the LongTermMemory CI failure fixed, main merged a second time

At the developer's request, `tracy_icra` was merged into `integrated-simulation-pipeline`
(#265) ahead of `tracy-demo-takes-the-integrated-branch`, whose own job this normally
would have been - the developer chose to bring it in now rather than wait.

**Eleven conflicted files, all resolved by reading both sides rather than picking one**
(`c719c44a9`):

- `segmind/detectors/base.py` - kept this branch's typed `predicate` parameter on
  `get_relation`; replaced the narrower `get_relation_to_holes` outright with
  `tracy_icra`'s more general `get_relation_to_regions`, since the general primitive
  subsumes the specific one rather than sitting beside it. Kept both `holes` and the new
  `hole_regions` fields on `SegmindContext` - they answer different questions (which
  apertures exist, versus which region each maps to).
- `segmind/detectors/spatial_relation_detector_nodes.py` - adopted `tracy_icra`'s shared
  `BaseHoleContactDetector` base for `HoleContactDetector`/`LossOfHoleContactDetector`,
  which removes the duplicated `overlap_threshold`/`additional_candidates` fields the two
  detectors previously each declared. Carried this branch's more specific docstring
  content into the merged base (the measured 0.17 overlap threshold, the 5 mm marker
  thickness) rather than losing it to `tracy_icra`'s more general prose.
- `segmind/detectors/atomic_event_detectors_nodes.py` - the one conflict that surfaced a
  real, pre-existing bug in **both** branches' own code, not just a design difference:
  `MotionDetector._is_lifting` called `poses[0].to_position().z`, and `NumericPose` has no
  `to_position` method - it is a plain dataclass whose `position` field is already a
  `Tuple[float, float, float]`. Fixed to read `poses[0].position[2]`/`poses[-1].position[2]`
  directly. `tracy_icra`'s new `LiftDetector`/`StopLiftDetector` were built on the same
  broken pattern and fixed the same way, and their `Pose.from_numeric_pose(...)` calls
  (needed because `MotionEvent.start_pose`/`current_pose` are typed `Pose`, not
  `NumericPose`) were kept as `tracy_icra` had them.
- `coraplex/execution_environment.py` - both sides' `ExecutionEnvironment` fields kept
  together (`real_time_pacing`, `real_time_factor`, `prediction_horizon` and, at the time,
  `max_ticks_per_motion_mapping`) since neither superseded the other. `max_ticks_per_motion_mapping`
  is removed again below, once main's merge made it dead.

**The LongTermMemory CI failure the developer flagged, fixed twice.** Merging #295's
`AgentInteractionEvent` in as a second base on `PickUpEvent`/`PlacingEvent`/
`InsertionEvent` (see the 2026-09-09 convergence entry above) broke ORMatic's
joined-table inheritance: `wrapped_table.py`'s `_original_wrapped_for_mapping` maps a
class to the SQL parent of the *first* already-mapped ancestor its `__mro__` reaches, and
it only supports one parent per class. With `EventWithEffect` listed first in each
class's bases, that first mapped ancestor was `EventWithEffect`, not
`AgentInteractionEvent`, so a long-term-memory query for `AgentInteractionEvent` found
none of the three event types.

First fix (`0e580a146`): reorder the bases so `AgentInteractionEvent` comes first on all
three classes. Verified in an isolated standalone class hierarchy before applying it -
`effect()` and `isinstance(event, AgentInteractionEvent)` both hold for all three.

Superseded by the developer's own, simpler fix (`12d806e20`): make `AgentInteractionEvent`
itself extend `EventWithEffect`. An agent's action always changes what holds of the
object, so the inheritance is true on its own terms, not just a workaround for ORMatic -
and it means `PickUpEvent`/`InsertionEvent` need only single inheritance from
`AgentInteractionEvent` alone, with no base ordering to get right. `PlacingEvent` keeps
`(AgentInteractionEvent, ComesToRestEvent)`, since it specifically needs
`ComesToRestEvent`'s effect logic, shared with plain `SupportEvent`. Verified again in
isolation, including the negative case: `SupportEvent`, a physics event with no agent
behind it, correctly stays outside `isinstance(..., AgentInteractionEvent)`.

**A fresh conflict against `origin/main` appeared after that push.** The developer said
yes to merging main in and resolving it now rather than leaving it. `51fc40548` merges
it, five files:

| file | what met | resolution |
|---|---|---|
| `coraplex/plans/executables.py` | main replaced `GiskardExecutable.max_ticks_per_motion_mapping` (a `ClassVar`) with `Context.ticks_per_motion` (a context field), per main's own `test_the_tick_budget_is_not_class_state`: *"The budget is a policy of the run, carried by its context, so two runs in one process cannot be given different budgets by class state that outlives them."* | adopted main's design in full - removed the old `ClassVar`, the `tick_limit` property and the `DEFAULT_MAX_TICKS_PER_MOTION_MAPPING` constant rather than keeping both mechanisms; kept this branch's pause-handling (`is_paused`) and real-time tick-pacing logic inside the loop, which main's side of the conflict did not carry |
| `coraplex/execution_environment.py` | not itself conflicted, but still carried `max_ticks_per_motion_mapping`/`previous_max_ticks_per_motion_mapping` and the matching `__enter__`/`__exit__`/`__call__` wiring from the `tracy_icra` merge above | removed, to complete the same migration - `GiskardExecutable` no longer has the class attribute this file was setting |
| `coraplex/robot_plans/actions/core/pick_up.py` | main added `allow_gripper_collision=True` to `_grasp_attempt_plan`'s closing `MoveGripperMotion`; this branch already sizes the same call's goal with `grasped_object=self.object_designator.root` | read `MoveGripperMotion`'s own class definition first to confirm the two are independent, pre-existing, complementary parameters (a collision permission and a goal-sizing hint) rather than alternatives - kept both. Also kept this branch's `if self.context.update_world_model_attachment:` guard around the trailing `ReAttachNode`, which main's side of the conflict had dropped entirely; keeping main's unconditional version would have been a silent regression |
| `test/coraplex_test/test_plan/test_executables.py` | this branch's two tests for the old tick-budget mechanism (`test_a_motion_is_given_a_finite_tick_budget_without_being_asked_for_one`, `test_an_execution_environment_budget_replaces_the_default`) versus main's new collision-avoidance tests and `test_the_tick_budget_is_not_class_state` | dropped the two old tests (they test a mechanism that no longer exists), kept all three of main's - no duplication, since this branch had no collision-avoidance tests of its own in this file |
| `test/coraplex_test/test_designator/test_motion_designator.py` | two independent new imports added on each side, both used later in the file (`ViewManager` on this branch, `ClosingMotion`/`OpeningMotion` on main) | kept both |

One remaining reader of the retired name was a docstring rather than code:
`experiments/tracy_experiments/trajectory_planning.py`'s `DEFAULT_MAX_TICKS` constant
referenced `GiskardExecutable.max_ticks_per_motion_mapping` by name in its own docstring;
repointed to `Context.ticks_per_motion`, completing the rename per AGENTS.md's "a rename
is finished only when every reader of the old name reads the new one."

**Verification.** Every file touched in this round was byte-compiled clean
(`python3 -m py_compile`) and re-checked for stray `<<<<<<<`/`=======`/`>>>>>>>` markers
before committing; ORMatic generation and anything importing ROS still needs a real CI
run, which this container cannot give. CI on `51fc40548` had not reported when this was
written; per the standing rule against scheduled checks, nothing was armed to watch it -
ask, or look at the run directly.

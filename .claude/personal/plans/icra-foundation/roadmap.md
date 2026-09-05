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

The memo's thesis is one mechanism: the same EQL query answers a question,
selects which backend answers each predicate, drives what the robot
perceives, and verifies the result in the digital twin; removing knowledge
produces failures the query predicts. Nothing before this plan owned the
experiments, the scenario definitions, the episode recording, the capability
routing, the physics verification, the failure taxonomy, the VLM baselines
or the artifact — see the predecessor's history for the full survey of what
`knowledge-directed-perception` already owned instead.

**This wave is the foot of the whole programme.** `integrated-simulation-pipeline`,
`scenario-domain-model` and `run-results-recorded-into-sql` can all start in
parallel with no dependencies, and every mechanism/experiment item in
`icra-mechanism`/`icra-evidence` stacks on one of the ten items here.

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
  perception tips so the rename lands over them.
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

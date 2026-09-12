# claude/trial-motion-recorded-3cqdmq - PR #319 merged into #265; branch restarted
# from the base for PR #323, the EQL coverage round (2026-09-12)

Base: `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265).
Session: https://claude.ai/code/session_013HepqhoucZF2H2cCjSizFP

## Done (original task)

1. giskardpy: `MotionStatechart.to_json`/`_from_json` carry `StateHistory`.
2. experiments: `RecordedTrial.motions: List[RecordedMotion]`; observer `ran_the_motion` +
   `ObserverMotionListener`; coraplex `GiskardExecutable.execute` tells
   `Context.motion_listener` (`ReceivesExecutedMotions`).
3. record_episode: `PerturbationChoice.LIGHTING_CHANGED` dropped.

## Done (CI round, 2026-09-12)

Both red jobs on #319 were red on the base branch too, byte-identical, and came from base
commits after the merge base. Fixed both here anyway:

4. `test_each_lib (version)`: `experiments` imports `physics_simulators` (base's
   `simulated_camera.py`) without declaring it. Declared it in `[project] dependencies`
   and the workspace group. Green in CI.
5. `test_each_lib (experiments)`: 4 failures in base's new `test_tracy_pickup_demo_mujoco.py`,
   all one root cause. `CAMERA_LINK_T_OPTICAL` assumed the plain link->optical quarter
   turns; against the `camera_link` `iai_tracy_description` states, all 8 shipped captures
   agree the real camera looked ~12 deg flatter and ~40 mm further along it. The simulated
   camera therefore looked too steeply, the board fell to the edge of the picture, and the
   look found 2 pieces instead of 4. Re-derived the constant from the captures against the
   frame the camera reports in (`tracy_mount`). File now 6 passed, 1 xfailed locally.
   Only `camera_on_tracy` reads the constant, so the real-robot demo is untouched.
   Why: the lab runs the camera against the description in Tracy's own ROS workspace on
   the lab machine, not the published one - answered by the developer, no longer open.

## Environment breakthrough (this container)

`iai_tracy_description` IS obtainable here after all: clone `code-iai/iai_tracy` (branch
`ros2-jazzy`), `UniversalRobots/Universal_Robots_ROS2_Description` (`jazzy`) and
`code-iai/ros2_robotiq_gripper` (`iai_dualarm`), then build a fake ament prefix with
`share/<pkg>` symlinks plus `share/ament_index/resource_index/packages/<pkg>` markers and
prepend it to `AMENT_PREFIX_PATH`. Tracy then parses and the Tracy tests run.
Scratchpad: `.../scratchpad/fake_prefix`.

Also: `psycopg2-binary` needed in `.venv` for the postgres URI; `service postgresql start`
then provision with `semantic_digital_twin/scripts/create_postgres_database_and_user_if_not_exists.sql`
(db `montessori_sorting`, user/password `montessori`).

## CI state (2026-09-12 06:38)

All 23 checks green on #319. The robokudo failure in between was
`test_query.py::TestQueryInterface::test_query` timing its 20 s action client out on a
loaded runner; one re-run of failed jobs passed it.

## Also proved this round

The headless Tracy run now works here: `record_episode.py --scenario robot-sorts-a-piece
--headless` against postgres recorded 4 motions with spans 7.35-443.70, 443.85-444.07,
444.33-446.03, 446.06-446.33 - the same count as the fixture. `MotionStatechartDAO` came
back with only `database_id` and `polymorphic_type`, confirming the database gap on Tracy
rather than only on the fixture. Local `test/experiments_test`: 1282 passed, 0 failed,
2 errors (both identical on base).

## Still open

A trial's chart does not survive the database (`MotionStatechartDAO` has no columns;
`from_json` needs a world the engine's JSON deserializer cannot pass; nothing fills
`Episode.world`). Not lost information though: a chart is reproducible from a saved plan
plus a saved world, so what the recording owes is the plan and the world. Reported on the
PR; separate change.

## Merge round (2026-09-12, after "fetch and merge 265")

Merged base `020cbc41a` (perceived-scene recording) into this branch: 3 conflicts, resolved
keeping both sides - `record_episode.py`/`test_record_episode.py` keep the dropped lighting
perturbation next to the base's `Layout`/`LayoutAsFound` and perceived-scene options;
`scenarios.py` keeps the base's `physics: ScenePhysics` rename next to this branch's
`motion_listener`. One test read `scenario.simulation.world`, renamed to `.physics.world`.
Merged-area tests (test_record_episode, test_montessori_watched_run,
test_montessori_scenarios, test_episode_observer, test_episodes): 171 passed, 0 failed.
Then merged this branch into `claude/icra-experiments-simulation-pipeline-w4ep7n` and
pushed that too, as asked.

## Answered by the developer

The camera calibration in use in the lab is the one in the description in Tracy's own ROS
workspace on the lab machine, not the published `iai_tracy_description`. So the 12 deg /
40 mm difference the captures show is that local calibration, and
`CAMERA_LINK_T_OPTICAL` carrying it is the right fix, not a mystery. Docstring and PR
description now say so; the open question is closed.

Motion statechart: a chart is deterministically reproducible from a saved plan plus a saved
world (load the plan from long-term memory, convert DAOs to domain objects and execute it,
or build the chart in the program). So the database gap is a gap in the reading, not lost
information, and what the recording still owes is the plan and the world. PR's "What is not
done" reframed accordingly.

## Answered this round: what the database holds and what EQL reaches (2026-09-12)

Asked: do the motions go to long-term memory as JSON, is the EQL/SQL reading tested, and
can EQL reach the controller's constraints from working memory?

Measured, not guessed (scratchpad `probe_motion_eql.py`, `probe_constraints_eql.py`):

- Not JSON. `to_dao` writes rows: `RecordedMotionDAO(database_id, start_moment,
  end_moment, polymorphic_type, _motion_statechart_id)`, joined to the trial through
  `RecordedTrialDAO_motions_association`; `MotionStatechartDAO` has only `database_id`
  and `polymorphic_type`. The schema does have JSON columns for scalar arrays (including
  `GiskardConstraintDAO.expression` and `NodeArtifactsDAO.observation`), but nothing
  writes a chart as a JSON document - `MotionStatechart.to_json` is the ROS wire
  (`motion_goal.py`, `feedback_publisher.py`, the inspector), not the recording path.
- EQL over the SQL backend does reach the motions. Verified both the to-many join
  (`contains(trial.motions, motion)` plus `trial.episode.identifier == ...`, which
  translates into a join across the association table) and a range condition on the
  spans. Untested before this round, so it is now two tests in
  `test/experiments_test/test_long_term_memory.py` under `# %% the motions a run ran`,
  pushed as `829f514c0` on the branch restarted from base `bb1bd5095`, draft PR #323
  (19 passed with test_long_term_questions.py alongside).
- Controller constraints: EQL can range over a built chart's `Task` nodes and its
  `GiskardEqualityConstraint`s when the variable is handed the domain (the chart's nodes
  or `combine_constraint_collections_of_nodes()`), including `contains` across a node's
  constraint collection. Two limits: nothing in the controller is a `Symbol`
  (`MotionStatechartNode`, `Task`, `GiskardConstraint`, `ConstraintCollection`,
  `MotionStatechart` all `issubclass(Symbol) == False`), so a working-memory question,
  which ranges over the symbol graph with `domain=[]`, finds nothing; and a condition on
  a symbolic field (`quadratic_weight`, `expression`, the bounds) raises
  `HasFreeVariablesError`, because EQL's truth test evaluates a casadi expression that
  still has free variables. Plain fields (`name`, `weight`) work.
- So the working-memory constraint question is not askable today. Two routes, developer's
  call: hand the question the chart as its domain, or make the controller's nodes and
  constraints symbols so the graph tracks them.

## Recommended approach for constraints and detectors (2026-09-12, asked for)

Asked: cleanest way to find all constraints of an action/task/motion and return their
expressions, and likewise the detectors that answered a perception query.

Measured first (scratchpad `probe_constraint_design.py`):

- The recommended query shape works today. A node that inherits `Symbol` registers
  itself, and `flat_variable(node.constraints)` selected the compiled constraint with
  `node.name == "hold the joint"` as the condition, returning its `expression` and
  `bound`. Reading the symbolic fields off the answers is fine; only conditioning on
  them raises `HasFreeVariablesError`.
- Registration is O(1) index bookkeeping (`SymbolGraph.add_node` does no field
  traversal). A `ClassDiagram` over all 122 `MotionStatechartNode` subclasses builds in
  0.61 s once.
- Long-term memory is not an option for expressions. `to_dao` on a live constraint
  builds a `GiskardEqualityConstraintDAO`, but the insert fails with
  `Object of type Scalar is not JSON serializable` - the generated `expression` column
  is a plain JSON column holding a `Scalar`. Even with a serializer,
  `SerializableSymbolicMathType.to_json` refuses any non-constant value, and a
  constraint's expression is never constant. So no constraint row has ever been
  written.

Recommendation given: keep the question in working memory; make
`MotionStatechartNode` inherit `Symbol` (one edit covers constraints and detectors,
since `Task`, `PerceptionTask` and `AbstractDetector` are all nodes); add a public
`MotionStatechartNode.constraints`, which also removes the private reach
`combine_constraint_collections_of_nodes` already performs from outside; give the node
a `parent` object in place of `parent_node_index` for the action/goal granularity, and
keep the plan-side link (`MotionNode` -> its `Task`) on the coraplex side rather than
teaching giskardpy the plan's vocabulary - `GiskardExecutable.motion_mappings` is that
link today and a dict is the wrong shape for it. On the perception side the provenance
does not exist yet to be queried: `Detection` carries only the annotation and the pose,
`PerceptionTask.perception_source` is `init=False`, the detections are applied to the
world and dropped, and `DetectionEvent` does not name the detector that produced it.

## Done (giskardpy constraint questions round, 2026-09-12)

Asked for the giskardpy half of the recommendation, with one change: query by constraint
*type*, never by name. Committed `5c058219d` on the same branch, pushed onto #323.

- `MotionStatechartNode(Symbol, SubclassJSONSerializer)`. Precedent already in the repo:
  `DetectionEvent(Symbol, ABC)` and `ManipulatesBodies(Symbol, ABC)` with the same
  rationale in their docstrings.
- `MotionStatechartNode.constraints` (public), `_constraint_collection` gets a
  `default_factory` so an unbuilt node answers `[]`, `ConstraintCollection.__iter__`, and
  `merge` now takes the constraints instead of another collection's `_constraints`.
  `combine_constraint_collections_of_nodes` uses the public accessor.
- `_CollisionAvoidanceTask` -> `CollisionAvoidanceTask` (public), so "all non-collision
  constraints" is `not_(HasType(task, CollisionAvoidanceTask))`.
- Four tests in `test/giskardpy_test/test_motion_statechart/test_constraint_questions.py`.
  Proven meaningful by TDD: with the `Symbol` base removed, 3 of the 4 fail with empty
  answers.

Corrections to what I told the developer last round: `MotionStatechartNode.parent_node`
and `.motion_statechart` already exist as object-returning properties, so no new parent
accessor was needed - `parent_node_index` is not a traversal dead-end.

Query-by-type vocabulary that already existed and needed nothing new: `enforcement_strategy`
(a `type[EnforcementStrategy]` field) tells `VelocityStrategy` apart from `IntegralStrategy`,
and equality vs inequality is already a class distinction.

Test evidence (ROS sourced): giskardpy test_motion_statechart/test_qp/test_orm/test_executor
483 passed, 14 failed, 91 errors - failure list byte-identical to the unmodified tree
(479 passed), every one of them this container missing robot descriptions or graphviz `dot`.
krrood_test 3080 passed / 2 failed (`dot`). segmind_test + experiments questions 131 passed.
Pre-existing and unrelated: running `test/krrood_test` together with
`test/experiments_test/test_long_term_memory.py` in one process fails collection with
`Table '_7893...' is already defined for this MetaData instance` - reproduced identically on
the unmodified tree.

## #323 is no longer a draft

It came back `draft: false` this round, so the developer marked it ready themselves. Per
"When your PR's job ends" I did not re-draft it after pushing. The giskardpy commit went
onto its branch because the session is pinned to `claude/trial-motion-recorded-3cqdmq` and
the developer asked for the work in this session; flagged in chat, with an offer to move it
to its own branch.

## Still open on the perception side

The developer clarified: not robokudo. What they want is, when writing an EQL query with
the perception backend, to know how each answer was detected - which detector, and a
mapping from a detector to the features/predicates/attributes it tried to answer. Their
read is that perception spawns new instances, so it fits EQL's inference explanation
mechanism (`Symbol._inference_explanation_`, `InferenceExplanation`). Not started.

## Merged into #265 (2026-09-12, asked for)

Merged `claude/trial-motion-recorded-3cqdmq` (5c058219d) into
`claude/icra-experiments-simulation-pipeline-w4ep7n`, which had moved on to 3e41b69e2
(#325, belief checked against perception). No conflicts - the two sides' file lists are
disjoint, 265 having touched only experiments/segmind and this branch only giskardpy plus
two test files. Merge commit 1425c5df9, pushed. Nothing pushed to #323's own branch, since
the developer took it out of draft.

Verified on the merge (ROS sourced): the four constraint-question tests plus the modules
265 changed (test_montessori_expectations, test_questions, test_question_scoring,
segmind test_expectations) 102 passed; test_long_term_memory with
test_montessori_watched_run, test_montessori_scenarios and test_record_episode 185 passed.

#265's description gained a "#323 merged in" section and this session's link; it is still
a draft and was left one. It reports `mergeable_state: dirty` against `main` and carries
`needs-resolution`, both from before this merge.

## Local test environment notes

`pytest` must be run with ROS sourced (`source /opt/ros/jazzy/setup.bash`), otherwise ORM
generation now dies on `CouldNotResolveType: MetaData` - base's generate_orm.py reaches
`semantic_digital_twin.exceptions`, whose `MetaData` hint only resolves when
`geometry_msgs` imports. Wrappers: `scratchpad/pytest.sh` (ROS only) and
`scratchpad/pytest_tracy.sh` (ROS + the fake ament prefix).

Also: with ORM interfaces generated locally, `test/version_test` reports `coraplex` missing
a `segmind` declaration - that import is in the generated, gitignored
`coraplex/orm/ormatic_interface.py`, which CI's version job never has. Local artifact only.


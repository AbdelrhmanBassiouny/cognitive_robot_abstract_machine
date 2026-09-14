# framework figure end to end (branch `claude/awesome-keller-2q7t9u`)

Four stacked draft PRs, each on the previous, the first stacked on #355
(`claude/insert-action-14xvqi`, the F1 branch). Goal: the open-plan CONFIG in
`experiments/doc/figures/framework/framework.typ` runs end to end in MuJoCo with
Giskard, every open slot closed by the backend that can answer it.

#355's one open review thread (r3999689257) delegates "an RDR fills the target hole"
to a follow-up PR - that is this work's stage 3 rules backend.

## Stage 1 - the syntax (PR #359, in review)

Done:
- One reading per question, each written once: `_as_operand_` (what a value contributes
  where an operation expects an operand - a match contributes the variable it describes)
  and `_as_expression_` (the expression it stands for - what quantifying, selecting and
  reading a bound value want). Everything that builds an expression goes through
  `_as_operand_`, predicates and symbolic functions included.
- A handed-over statement carries its narrowing: `Query._narrowings_mentioned_in_` takes
  on what the statements a condition mentions say, transitively and once each, skipping
  the statement the query is about. `Variable._describing_statement_` (declared by
  `HasNarrowings`) is the link back. `Match.where` records them too, so generative
  backends still read what a statement says off the match.
- `Match._nested_matches_`; `PlanNode.underspecified_actions` / `open_descriptions`; no
  `underspecified()` wrapper and no `UnderspecifiedPlan`.
- Figure CONFIG says `sequential([...])`, `an(InsertionAction)`, `shape_category=`,
  `.from_(board.apertures)`; `framework.pdf` rebuilt.
- `watch_narrowing` and `scene_publishing` reach for nothing private.
- Local ROS stubs live in the scratchpad only (never committed) and must be on PYTHONPATH
  for `scripts/regenerate_all_orm.py` and any test run, or ORM generation dies on
  `CouldNotResolveType: MetaData`.

Review round 2 (2 threads): the `._symbolic_expression_` one handled and resolved; the
`InsertionAction` one renamed in #355 (`634f0aa708`) and merged here, but left open
because #355's CI is not green.

#355's base had moved; the merge conflict is resolved and pushed (`48b125cece`), and the
base was merged again after its camera fix (`e57ed84b08`, up here as `74c4e28c0c`; the
conflict was `_SortingRig.sort` - this branch's `insertion: Insertion` signature plus the
base's new `__post_init__`).

#355 CI: 16 failures, all in experiments, none of them the stack's own. Five are the
insertion ones, addressed by two bug PRs off main, both merged into #355:
- #362 `NoValueAlongAccessPath` - the bare `next` in
  `MappedVariable.apply_mapping_on_external_root` turned into
  `RuntimeError: generator raised StopIteration`.
- #364 `Symbolic.names_one_element` - a StrEnum member was iterated character by
  character, so `Value cylinder not in domain` with cylinder in the domain. Reproduced
  locally on a board built from measurements (no robot needed):
  `a(InsertionAction)(target=<hole>, arm=...)` now evaluates under ProbabilisticBackend.

The rest are one defect of the base branch, fixed there on 2026-09-13 (`7aa4013ae8`):
`CAMERA_LINK_T_OPTICAL` *stated* the offset from Tracy's `camera_link` to the colour
camera's optical frame, and that offset is the difference between where a description
puts `camera_link` and where the camera stands, so it moves with every recalibration.
The committed value holds against the lab's own ROS workspace; CI builds against the
published `iai_tracy_description`, which puts `camera_link` a twelfth of a turn and most
of a metre away, so the simulated camera looked 12 degrees flatter: board 52 mm out, two
of four pieces unfound, nothing through its hole, trial failed. `camera_link_T_optical`
now derives the offset from the captures (all eight agree to 1e-7 on where the camera
stood in Tracy's own frame) against the description in hand. Pinned by
`test_the_camera_stands_where_the_capture_says_wherever_its_mount_is_stated`, which
states the mount at two places a metre apart; it needs no description, so it runs here.

**Correction to an earlier note: #286 is NOT the fix for those camera failures.** It fits
the real camera's ~1.7 degree lean out of a measured surface and its own description
reports the same four failures as ones the base already carries. Nothing of it was merged
into #265.

Base CI is the only place the other four `test_tracy_pickup_demo_mujoco.py` tests can run
(they need `iai_tracy_description`), so whether the camera fix clears them is unverified.

## Stage 2 - one backend per open slot (PR #366, draft, branch
`claude/one-backend-per-open-slot`, on #359)

Done:
- `BackendChoice` is itself a `QueryBackend`, so it drops into
  `Context.query_backend`. It answers each description a statement hands over with the
  first of its backends that declares it can, innermost first, and the answer stands in
  its place in the statement that handed it over. `answered` keeps which backend
  answered which statement; `NoBackendAnswers` when none declares it can.
- `Match.answering(description, answer)` restates over the *same variable*, which is
  what keeps the statement's conditions - they are written about that variable, and
  `stating` drops them (re-applying them to a `stating` copy answers nothing at all).
  `DescriptionNotStated` when the statement hands that description over nowhere.
- `PerceptionBackend` now binds what its look reports as a type parameter
  (`PerceptionBackend[MontessoriDetection]`), like `PerceptionDetector` binds its look,
  so its capability is about that kind. Without it every look answers `True` to every
  match and the order of the list decides everything.
- `_nested_matches_` unchanged; its direct half split out as `_stated_matches_`.
- Tests: `test/krrood_test/test_eql/test_statement_answered_by_several_backends.py` (11),
  over mimics in `test/krrood_test/dataset` only. Whole `test/krrood_test`: 3117 passed,
  2 failed - both `test_object_diagram.py`, both `graphviz ... ExecutableNotFound: dot`,
  both red the same way before this. Montessori perception + narrowing: 65 passed.

## Stage 3 - four backends, one per slot (PR #368, draft, branch
`claude/four-backends-close-the-slots`, on #366)

Done, all headless (no ROS, no MuJoCo):
- `experiments/open_slots/world.py` - `WorldBackend`, selective, answers a statement
  about the things the world holds (the look's findings among them once stood there), so
  `SupportedBy` is read off two bodies' boxes. Capability = a kind of thing this world
  holds, which is a knowledge-state precondition.
- `experiments/open_slots/holes.py` - `Admits(hole, piece)` triple, `PieceToSort` case,
  `HoleShapeRules` (an `EQLSingleClassRDR` like `DetectorRules`, with an `Expert` whose
  condition is "every piece shaped like this one"), and `HoleRulesBackend`. Neither
  selective nor generative: it supplies the open `shape_category` from the rules, then
  selects. `add_rule` is the corrigibility, and it is tested.
- `experiments/open_slots/choice.py` - `backends_for(looking, world)`: look, world,
  rules, probabilistic, in that order and for stated reasons.
- `BackendChoice.backend_for` made public (which backend answers a slot is the thing
  worth asking).
- Tests: 5 + 6 + 5 new, plus 2 added to `test_montessori_perception_backend.py` (40
  there). `test/version_test/test_dependency_declarations.py`: 20 passed.

Answers #355's open thread r3999689257 ("an RDR fills the target hole").

## Stage 4 - the open plan runs (PR #369, draft, branch
`claude/the-open-plan-runs`, on #368)

Rewritten by the refactor round below. What stands now:
- `experiments/open_slots/plan.py` - `sorting_plan(board, lid, arm, end_effector)`,
  the figure's whole plan written once: `sequential([a(PickUpAction)(...),
  an(InsertionAction)(...)])` with all its slots open.
- `coraplex.plans.plan_node.PlanNode.grounded_by(backend)` - the general machinery that
  answers a stated plan.
- `experiments/scripts/framework_demo.py` - builds the simulated lab, looks, writes the
  plan and grounds it, reporting which backend answered which slot.
- `framework.pdf`/`framework.typ` untouched by this stage.

## Review round on #369 (thread r4001095327, handled and resolved)

The ask: the underspecified statement given to the RDR must have full context - access
to the parent matches it is inside of - and generally, not hard-wired for this case.

Done across the three PRs it belongs to:
- **#366 `252a5d5bb7`**: every `Match` carries `_stated_by_` (the statement handing it
  over + the attribute it is stated to, a `StatedBy`) and `_enclosing_statements_`
  (innermost first). Written in `__call__`, so it is there before anything asks, and
  `_restated` carries it on. 7 tests in `test_a_description_knows_what_it_is_for.py`.
- **#368 `72894f888f`**: `HoleRulesBackend.piece_the_hole_is_wanted_for` walks the
  enclosing statements; `Admits` deleted (it existed only to carry the piece). The
  backend takes the world so a statement naming a body says which piece too. Dropping
  `Admits` also untangled shape from size: `fits_through` demands a matching category,
  which made a *corrected* rule unanswerable; now the rules say the shape and the
  measurements say which holes of that shape the piece passes through, closest fit
  first, and the corrigibility test asserts the correction takes effect.
- **#369 `7c904e11e6`**: the run states
  `an(InsertionAction)(object_designator=piece.root, target=<hole description>)` and
  asks for the one slot it leaves open. Figure CONFIG reverted to what it already said;
  PDF rebuilt. `sorting.py` now imports coraplex robot plans, so that test file needs
  ROS (CI has it; here the scratchpad stubs).

## Review round on #368 (3 threads, all handled and resolved)

- **"It should also condition that this is for an Insertion Action"** (`holes.py`
  capability) -> `e62fb39805`: capability is now three parts -
  `describes_a_hole_of_no_stated_shape` + `wanted_as_the_target_of_an_insertion`
  (`_stated_by_.attribute_name == "target"` and the enclosing type is an
  `InsertionAction`) + a piece being readable. The dataset mimic
  `PuttingAPieceThrough` is now the negative case. Cost: `holes.py` imports coraplex
  robot plans -> `rclpy` at import, so the two hole tests need ROS (CI has it; here the
  scratchpad stubs). Offered, not done: carrying "it is for an insertion" into
  `PieceToSort` so a *rule* can condition on it.
- **"Why only semantic annotations? How is this different from the symbol graph?"**
  (`world.py`) -> same commit: `everything_it_holds` now yields kinematic structure
  entities, connections, degrees of freedom, actuators and annotations, filtered by the
  statement's kind (a `a(Body)()` used to answer nothing). The symbol-graph answer,
  verified: it is one singleton per process, so a native answer returned pieces from
  *both* of two worlds while the backend returned only the first world's. Written into
  the class docstring and pinned by
  `test_a_thing_standing_in_another_world_is_not_among_the_answers` (asserts only the
  scoped side - the symbol graph accumulates across a pytest process).
- **"'a' not 'an'"** -> `9fe389c889` on #366: every `an(TakingHoldOf...)` is `a(...)`;
  `an` no longer imported in those two files. Pre-existing `an(Sighting)` in
  `test_backend_that_answers_by_looking.py` left alone.

Regression after the round: 1602 passed, 3 skipped across `test/krrood_test/test_eql`,
the stack's experiments tests, montessori perception/narrowing/imagination and
`test/version_test`.

## Refactor round on #369 (the plan in one place, no hand-made classes)

The ask: the whole plan written in one place exactly as the framework image has it, and
no more classes hand-made for this plan - that is faking the work and hard-wiring it.

Done, all on #369 except the `Role` reading, which belongs to #368:
- **`coraplex.plans.plan_node`**: `PlanNode.grounded_by(backend)` grounds a stated plan
  - every open description answered once, innermost first, standing in its place in
  *every* action that hands it over, then each action constructed. So two actions
  naming one description act on the one thing. `_actions_it_states` is the plan-wide
  gather `open_descriptions` already did inline. 9 tests in
  `test/coraplex_test/test_plan/test_underspecified_plan.py` over its own
  `PostingSlot` dataset.
- **`experiments/open_slots/plan.py`** (new): the figure's plan, whole, in one
  function. `experiments/open_slots/sorting.py` (`SortingByAnOpenPlan`) deleted, and
  with it `SceneAlreadyStood`.
- **Reverted**: `PerceivedSorting.hole_for` and `SimulatedPickupDemo.sorting_over`,
  the two hooks carved into shared classes for that deleted subclass. Both files are
  now byte-identical to #368's.
- **`framework_demo.py`** rewritten: no subclass of anything, just lab -> look -> plan
  -> ground -> report.
- **`holes.py`**: `piece_standing_for` also reads a piece off a `Role` of it, since
  what a look answers with is a role of the piece.
- Tests: `test_the_plan_the_figure_shows.py` (6, headless, over the rendered scene
  fixtures) replaces `test_sorting_by_an_open_plan.py`.

What the refactor exposed, and did not fix:
- The plan grounds to three slots, not four: the figure draws the *simulation* slot
  nested inside the perception slot, and it is - `SupportedBy` is a `.where` condition
  the look checks in the imagined world it stood its finding in, not a description
  handed over. So `backends.answered` names three backends (look, probabilistic,
  rules); `WorldBackend` is in the choice but this plan does not reach it.
- The demo resolves the plan but does not perform it. `ImaginedWorld.copied_from`
  deep-copies, so the piece the look answers with stands in a copy of the world the
  robot plans in, and `PiecePublisher.publish_piece` builds a *separate* piece in the
  belief. The two halves are not joined, so the grounded `object_designator` is not
  something the arm can be driven at. The previous demo hid this by running the old
  hand-coded pipeline and asking the backends for the hole slot alone. **Closed by the
  round below.**
- The plan states three things the figure elides: `arm` on the insertion,
  `end_effector` on the grasp, and the surface as the lid body the look names rather
  than as `board`. **Closed by the round below** - the figure now states all three.

Regression: 1491 passed + 3 skipped (`test/krrood_test/test_eql`, `test/version_test`),
113 passed (the stack's experiments tests + montessori perception/imagination/
narrowing), 9 passed (coraplex underspecified plan).

## Joining the two halves (the piece a look answers with is the robot's own)

The ask: fix the two things the refactor exposed - the demo resolving rather than
performing, and the figure eliding three fields the code states.

Done, all on #369 (every perception file it touches is introduced far below the stack,
at `claude/icra-experiments-simulation-pipeline-w4ep7n`, so there is no lower PR of this
stack's own to fold it into):
- **The join.** `PiecePublisher.publish_piece` now takes the scene, and the finding it
  stood comes to name the piece the published world holds; the body the look stood for
  the sighting in a world of its own leaves that world. So `DetectedMontessoriShape`'s
  role taker is the belief's piece, and `object_designator.root` is a body the arm can
  be driven at.
- `ImaginedWorld.remove` leaves alone a piece it does not itself hold, since the
  published world has taken it on; `MontessoriPerceptionBackend.discard` therefore no
  longer removes a rejected finding from the robot's world (a statement rejecting a
  piece says it is not what was asked for, not that the piece is gone).
- `PerceivedScene` keeps what the look found (`seen`) and offers it as `last_look`, a
  `FixedScene` a statement about the scene is answered from. `framework_demo.py` grounds
  the plan against that rather than taking a second look, so the run looks once.
- **The figure** now states `arm=LEFT` on the insertion, `end_effector=LEFT_HAND` on the
  grasp, and `SupportedBy(shape, lid)`; `framework.pdf` rebuilt. `plan.py`'s caveat
  paragraph about the elided fields is gone, because there is nothing left to caveat.
- Tests: `test_the_piece_a_finding_names_is_the_one_the_published_world_holds` (scene
  publishing, over a shipped capture) and
  `test_the_piece_it_picks_up_is_one_the_world_the_robot_plans_in_holds` (the plan,
  end to end over `displaced_cube_from_hole`, headless).

## The plan performs (still #369)

The ask: make the plan performable on the demo, and film it from the robot's camera and
from a front view.

Done:
- **`ActuatorDrivenAction`** in `pick_and_place_action.py`: a `SubClassSafeGeneric`
  family whose members bind the plan action each carries out (`PickUpActionMujoco` ->
  `PickUpAction`, and so on). `ActuatorDrivenAction.performing(resolved, simulation,
  actuators)` turns a resolved plan into the actions that drive this lab, and
  `NoActionCarriesItOut` where nothing does.
- **The grasp is read.** `_top_down_pose_builder` -> `_grasp_pose_builder(world, robot,
  arm, grasp)`, turned by `grasp.grasp_orientation()`; all three MuJoCo actions now take
  a `grasp_description`. The old fixed `pitch=pi` is exactly `RIGHT`+`TOP`, so the
  existing demos (all `FRONT`+`TOP`) now grasp rotated 90 degrees about the vertical -
  `test_tracy_pickup_demo_mujoco.py` is the check on that.
- **The plan says the hand comes down on the piece** (`FROM_ABOVE = TOP`), since a piece
  resting on a surface offers the fingers nothing else; only the approach direction is
  sampled, and every sample is then performable. Both actions state the one grasp.
- **`sorting_plan` takes the piece set.** `PIECE_COLOR` was the full-size set's cyan
  while the lab runs `SMALLER_PIECES` (blue), so `Colored` rejected every finding and
  the plan grounded to nothing. This was the real reason the demo had never performed.
- `backends_for` loads the generated ORM interface (a local import, the sanctioned
  exception): the probabilistic backend reads a stated object - the hand - through its
  DAO, and a plain `python -m` run had never imported one.
- `RealTimeSimulation.simulated_time` made public, so a film stamps its frames by the
  simulation's clock.
- `SimulationFilm` widens the offscreen buffer for its own frames instead of relying on
  the camera having done it.
- **The demo moved into the package**: `experiments/scripts/framework_demo.py` ->
  `experiments/src/experiments/tracy_experiments/framework_demo.py`, so it is importable
  and testable; `FrameworkDemo` builds the lab, looks, grounds, carries out and films.
  Two films at 960x544 (both sides a multiple of sixteen, so the codec does not resize):
  `robot_camera.mp4` and `table_from_the_front.mp4`, the latter from a camera at
  (1.7, 0.12, 1.38) looking at (0.7, 0.12, 0.95).
- **The figure**: `vertical_alignment=TOP` stated, `grasp_description=grasp` /
  `grasp_description=grasp_1` on both insertions, the fourth grasp bar is now `BACK/TOP`
  (the placeholder `FRONT/NONE` is excluded by the plan). PDF rebuilt.
- Tests: `test_framework_demo.py` (7, performs the whole run), 4 added to
  `test_the_plan_the_figure_shows.py`, 2 to `test_tracy_pick_and_place_action.py`, 1 to
  `test_tracy_real_time_simulation.py`.

Verified in this container: MuJoCo renders headless with OSMesa (`apt install
libosmesa6`, `MUJOCO_GL=osmesa`), and Tracy parses from clones of `code-iai/iai_tracy`
(branch `ros2-jazzy`), `UniversalRobots/Universal_Robots_ROS2_Description` and
`PickNikRobotics/ros2_robotiq_gripper` on `AMENT_PREFIX_PATH`, with a real
`ament_index_python` shim in the scratchpad rather than the dumb stub (the dumb stub is
what produced the 15 `get_package_share_directory` errors earlier sessions saw). The
baseline pickup demo run before any change: cube, cylinder and rectangular prism all
1.0, triangular prism 0.0 (its own xfail), 1168 s.

## Open review thread on #368 (r4002576823, awaiting a decision)

"Index the symbol graph by the world it has" for `WorldBackend.everything_it_holds`.
Checked: every kind of thing a world holds carries the `_world` backreference, so the
premise is sound. Replied with two routes and the hazard they share - an entity's world
is set by `add_to_world` *after* `Symbol.__new__` files the node, so any index keyed on
it has to be told when the key moves:
- **A** (recommended): a general keyed index in `SymbolGraph` - `index_by(key_of)` saved
  under the key function itself, `refile(instance)` - plus `WorldEntity.add_to_world` /
  `remove_from_world` calling `refile`, and a public `WorldEntity.world`. krrood stays
  self-contained because the key function is the caller's. Exact.
- **B**: the index in the backend with weakrefs, rebuilt when `World.revision` moves
  (needs that made public). No krrood change, but only as good as the invariant that
  every change to what a world holds advances the revision.
Thread left open; implement whichever is chosen, with the index pinned by tests (in
krrood over its own mimics for A).

## The stack as it stands

#355 -> #359 (stage 1) -> #366 (stage 2) -> #368 (stage 3) -> #369 (stage 4), all
drafts. Each PR's base is the branch below it. All three descriptions rewritten after
the review round.

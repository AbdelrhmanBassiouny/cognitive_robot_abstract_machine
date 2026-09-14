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

Done:
- `experiments/open_slots/sorting.py` - `SortingByAnOpenPlan`, which states
  `a(ShapeSortingHole)(shape_category=...).from_(board.apertures).where(Admits(hole,
  piece)).ordered_by(hole.cross_section_size)` and takes the first answer. Only which
  hole is meant is asked for; the hover arithmetic is unchanged.
- `PerceivedSorting.hole_for` extracted (the step it overrides);
  `SimulatedPickupDemo.sorting_over` extracted (the extension point the demo overrides).
- `experiments/scripts/framework_demo.py --execution simulated`, logging which backend
  answered which slot.
- The figure's target slot now carries `.where(Admits(hole, shape))`; `framework.pdf`
  rebuilt (typst is installed in the venv, so the figure builds here). `framework.svg`
  and `.png` are not tracked - do not add them.
- Tests: `test_sorting_by_an_open_plan.py` (4, headless) + `SceneAlreadyStood` mimic in
  the test dataset. `test_tracy_pickup_perceived_sorting.py` 9 passed.

Not done, deliberately:
- The MuJoCo run itself is unverified: `pickup_demo_mujoco` needs `rclpy` to import
  (the scratchpad ROS stubs make it importable, and the 21 MuJoCo tests still collect)
  and Tracy's description to build a lab, which this checkout has not. No slow
  end-to-end MuJoCo test was added - one that cannot be run or debugged here is worse
  than none.
- The figure's resolved plan is still written into the CONFIG by hand; feeding the
  run's own numbers back as JSON needs a run first.

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

## The stack as it stands

#355 -> #359 (stage 1) -> #366 (stage 2) -> #368 (stage 3) -> #369 (stage 4), all
drafts. Each PR's base is the branch below it. All three descriptions rewritten after
the review round.

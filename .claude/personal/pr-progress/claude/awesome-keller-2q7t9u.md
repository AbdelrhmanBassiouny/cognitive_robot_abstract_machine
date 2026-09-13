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

## Stages 2-4 - not started

2. A routing backend in krrood over an ordered list of backends, picking by
   `capability()` / `backend_supplies`, innermost open match first, recording per slot
   which backend answered; named exception when none can.
3. The four backends wired in experiments (perception, imagined world, probabilistic,
   RDR rules), each with a capability test.
4. `experiments/scripts/framework_demo.py --execution simulated`, the episode scenario,
   the figure's data JSON, the rebuilt PDF, one slow end-to-end MuJoCo test.

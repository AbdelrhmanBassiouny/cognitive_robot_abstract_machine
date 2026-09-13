# framework figure end to end (branch `claude/awesome-keller-2q7t9u`)

Four stacked draft PRs, each on the previous, the first stacked on #355
(`claude/insert-action-14xvqi`, the F1 branch). Goal: the open-plan CONFIG in
`experiments/doc/figures/framework/framework.typ` runs end to end in MuJoCo with
Giskard, every open slot closed by the backend that can answer it.

#355's one open review thread (r3999689257) delegates "an RDR fills the target hole"
to a follow-up PR - that is this work's stage 3 rules backend.

## Stage 1 - the syntax (PR #359, in review)

Done:
- `Match._operand_` / `HasSymbolicOperations._operand_`: a match handed to a predicate
  or a `@symbolic_function` now stands for the variable it describes, instead of being
  silently built into a concrete predicate holding the match object. Callers write
  `Colored(shape, ...)` rather than `Colored(shape._variable_, ...)`.
- `Match._nested_matches_`: the matches a pattern hands over, innermost first.
- `PlanNode.underspecified_actions` (empty unless the node stands for a statement) and
  `PlanNode.open_descriptions` over the node and its descendants.
- Figure CONFIG renamed to the tree's own names and `framework.pdf` rebuilt.
- Local ROS stubs live in the scratchpad only (never committed); without them this
  container cannot import coraplex or build the ORM interfaces.

Review round 1 (5 threads, all handled):
- `watch_narrowing` no longer reaches for `._symbolic_expression_`: the two holes are
  plain `variable(Body, ...)` like the lid, with their names stated as conditions in the
  one `where`. `one_condition_at_a_time` carries conditions about other variables into
  every step, so the demo keeps the same steps.
- No `underspecified(...)` wrapper and no `UnderspecifiedPlan`: a plan answers for
  itself. The figure reads `sequential([...])`.
- Test fixtures dropped; each test writes its own statements. `an(InsertAction)`,
  `a(Sighting)`, and no empty `()` where there is no pattern.

Decided with the user: no `LIGHT_BLUE` member. The cube measures `#00FFDD` (hue 172),
which reads as `CYAN`; the plan and the figure say CYAN. The renamings
(`shape_category=`, `.from_(board.apertures)`) were accepted.

Known gap, raised not fixed: a *foreign* match that carries its own narrowing, handed as
a predicate operand, contributes only its variable - the narrowing lives on the match's
own lowered query. Nothing in the tree does that any more. Fixing it properly means
hoisting such a match's conditions into the enclosing statement; offered as its own PR.

## Stages 2-4 - not started

2. A routing backend in krrood over an ordered list of backends, picking by
   `capability()` / `backend_supplies`, innermost open match first, recording per slot
   which backend answered; named exception when none can.
3. The four backends wired in experiments (perception, imagined world, probabilistic,
   RDR rules), each with a capability test.
4. `experiments/scripts/framework_demo.py --execution simulated`, the episode scenario,
   the figure's data JSON, the rebuilt PDF, one slow end-to-end MuJoCo test.

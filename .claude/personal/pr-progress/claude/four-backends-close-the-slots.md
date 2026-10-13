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

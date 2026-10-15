# EQL planning: roadmap

A goal is an EQL condition, and a planner is an EQL backend that answers it with a plan.
The design, the concepts behind it and the decisions taken are in the
[EQL planning plan doc](https://claude.ai/code/artifact/559b21dc-0e6c-41ce-9843-b06cb69fe62e).

## Rules every item follows

- The planner lives in `krrood.planning`, stays domain-agnostic and keeps `krrood`
  self-contained: no imports from coraplex, cramph or semantic_digital_twin there.
  The core fits the light install; continuous and probabilistic parts go behind `krrood[all]`.
- State is a valuation of fluents. A `State` overlay stores only changed fluents and is read
  through EQL's evaluation context; it never mutates the live objects or the `SymbolGraph`.
- Effects are assignments (`obj.attribute := value`, optionally conditional). Fluents nobody
  assigns persist. Derived facts are EQL rules or symbolic functions and never appear in effects.
- Actions declare explicit `effects()`, separate from coraplex's `post_condition` monitors,
  with a check that the effects imply the post-condition.
- EQL gives the meaning; search runs on a compiled integer state, not on EQL per step.
- Native planner first; the `unified-planning` backend after it.
- Working paper claims: one EQL expression serves as goal, precondition, constraint, monitor and
  explanation (1), and planning inside cramph statecharts through Achieve nodes with replanning
  (3); RoboCasa goals from the benchmark's own success checks are the evaluation (4).

## Dependencies outside this plan

- eql-performatives: `plannode-performable` (#15) is retargeted to cramph's `StatechartNode`
  (decided Oct 15); `giskardpy-acts` provides the Achieve and Monitor acts.
- Jonas Dech's cramph work on `Tigul/plan-cramp-second-iter` (statecharts, converted coraplex
  actions, the RoboCasa condition survey) gates the cram-robocasa track.
- #511 (EQL showcase) holds `SortPieceAction`; #261 (scenario model) is the RoboCasa harness.
- basstler-package and actions-budget reach a stable state first (Oct 15-31); the other tooling
  plans pause until the freeze.

## Calendar

- AAMAS 2027 rebuttal: Nov 20-24 (notification Dec 21, camera-ready Jan 25), inside the
  Montessori block, which therefore runs Nov 16 to Dec 2.
- Feature freeze Dec 18; January for constraints, the Fast Downward comparison, experiments
  and writing; IROS 2027 deadline to confirm.

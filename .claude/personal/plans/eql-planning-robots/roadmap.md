# EQL planning on robots: roadmap

- Builds on eql-planning (#513): State, ActionSchema and PlanningBackend come from krrood.planning and are never forked here. Design and readings: https://claude.ai/code/artifact/559b21dc-0e6c-41ce-9843-b06cb69fe62e
- Actions declare explicit effects(), separate from coraplex's post_condition monitors, with a check that the effects imply the post-condition.
- Planning enters execution only through an Achieve(goal) node in cramph statecharts, which plans when expanded and replans when a step fails; eql-performatives' giskardpy-acts provides the Achieve act.
- RoboCasa goals come from the benchmark's own success checks, never hand-written; the slice runs on the #261 scenario harness.
- Depends on Jonas Dech's cramph (Tigul/plan-cramp-second-iter) and #511 (SortPieceAction); icra-upstream lands coraplex onto cramph.
- Montessori Nov 16 - Dec 2 (the AAMAS rebuttal Nov 20-24 falls inside it), cramph and RoboCasa Dec 3-18, feature freeze Dec 18, IROS experiments and writing in January.
- Working paper claims: one EQL expression serves as goal, precondition, constraint, monitor and explanation; planning inside statecharts with replanning; RoboCasa goals from success checks as the evaluation.

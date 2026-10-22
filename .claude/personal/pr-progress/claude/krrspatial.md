PR #526 (ready, user-approved; base claude/krrspatial-interfaces = #527): SemDT's casadi spatial types in krrspatial[casadi]. Plan: domain-models.

Plan
- Spatial types behind the [casadi] extra on #527's base; Point2 implements PlanarPoint[ReferenceFrame, Scalar].

Done
- Merged #527, pushed 144a41d122; description rewritten. krrspatial 20 pass; SemDT 896 pass (rest missing ROS/robot packages).

Next
- Read CI (SemDT ORM build, giskardpy). Promote after #527 lands upstream.

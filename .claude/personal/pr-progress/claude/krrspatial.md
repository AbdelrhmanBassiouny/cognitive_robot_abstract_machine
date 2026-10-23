PR #526 (user-marked ready; base claude/krrspatial-interfaces = #527): SemDT's casadi spatial types in krrspatial[casadi]. Plan: domain-models.

Plan
- Point2 is PlanarPoint[ReferenceFrame, Scalar] (coordinate_system); HomogeneousTransformationMatrix is CoordinateChange[ReferenceFrame].

Done
- Merged #527's new base, pushed 015b915efe; description rewritten. krrspatial 32 pass; SemDT 896 pass (rest missing ROS/robot/ORM).

Next
- Read CI (SemDT ORM build, giskardpy). Promote after #528 and #527 land upstream. World as EuclideanSpace waits on the user (plan item world-as-euclidean-space).

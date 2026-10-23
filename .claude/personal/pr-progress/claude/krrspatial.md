PR #526 (user-marked ready; base claude/krrspatial-interfaces = #527): SemDT's casadi spatial types in krrspatial[casadi]. Plan: domain-models.

Plan
- Point2 is PlanarPoint[ReferenceFrame, Scalar]; HomogeneousTransformationMatrix is RigidCoordinateChange[ReferenceFrame], docstring warns it must be rigid.

Done
- Merged #527, pushed 753a4ce359; description rewritten. krrspatial 42 pass; SemDT subset 465 pass, same with and without the change.

Next
- Read CI (SemDT ORM build, giskardpy). Promote after #528 and #527. Optional: check numeric matrices are rigid (separate PR). World as EuclideanSpace waits on the user.

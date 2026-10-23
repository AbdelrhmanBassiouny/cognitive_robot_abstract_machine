PR #526 (user-marked ready; base claude/krrspatial-interfaces = #527): SemDT's casadi spatial types in krrspatial[casadi]. Plan: domain-models.

Plan
- Every SpatialType is CoordinateRepresentation[ReferenceFrame]; HTM is RigidCoordinateChange[ReferenceFrame]. Frameless values stay (user chose option c).

Done
- Pushed b77b55cc8d: coordinate_system on all spatial types, renamed and added transformation tests. krrspatial 55 pass; SemDT subset 908 pass, same as before.

Next
- Frame check in HTM.dot held for the frame-checked-arithmetic item: SemDT test_reference_frames asserts the opposite; waits on the user and Simon (doc UW7BdpNyW1r2sc63ktzA9T). Threads at 576 and 874 move to the spatial-action item. Read CI.

PR #526 (user-marked ready; base claude/krrspatial-interfaces = #527): SemDT's casadi spatial types in krrspatial[casadi]. Plan: domain-models. Keep mergeable with main.

Plan
- Every SpatialType is CoordinateRepresentation[ReferenceFrame]; HTM is RigidCoordinateChange[ReferenceFrame]; ReferenceFrame.express brings values into a frame. Frameless values stay.

Done
- Merged main (#518 ported into krrspatial), pushed 009739e57e. krrspatial 56 pass; SemDT 1114 pass, failures env-only.

Next
- Frame check waits on Simon (frame-checked-arithmetic); threads 576/874 go to spatial-action. Discussing groups and dimensions (SE(n), SO(n)) with the user. Read CI.

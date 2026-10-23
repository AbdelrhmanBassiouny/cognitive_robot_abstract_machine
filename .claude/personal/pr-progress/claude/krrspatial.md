PR #526 (user-marked ready; base claude/krrspatial-interfaces = #527): SemDT's casadi spatial types in krrspatial[casadi]. Plan: domain-models. Keep mergeable with main.

Plan
- Every SpatialType is CoordinateRepresentation[ReferenceFrame]; HTM is RigidCoordinateChange[ReferenceFrame]; ReferenceFrame.express brings values into a frame. Frameless values stay.

Done
- Pushed d313e8f49b: touched SemDT files import from krrspatial; Point/Point2.transform docstrings state the projection cases. krrspatial 56 pass, SemDT spatial 453 pass.

Next
- Open threads wait on later items: express space check (world-as-euclidean-space), imports (krrspatial-imports), 576/874 (spatial-action), 681 and 88 (Simon). Read CI.

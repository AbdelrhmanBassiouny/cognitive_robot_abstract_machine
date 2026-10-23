PR #527 (user-marked ready, base main): krrspatial's casadi-free base. Plan: domain-models, item planar-point-interface.

Plan
- Space (EuclideanSpace, ImagePlane), CoordinateSystem[SpaceT] (ReferenceFrame, ImageCoordinateSystem), CoordinateChange[CoordinateSystemT], PlanarPoint[CoordinateSystemT, CoordinateT].

Done
- Pushed c1c29715f5 (#528 merged in); 22 krrspatial tests pass; #526 and #524 merged it.

Next
- Read CI. Promote after #528, before #526/#524.

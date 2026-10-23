PR #527 (user-marked ready, base main): krrspatial's casadi-free base. Plan: domain-models, item planar-point-interface.

Plan
- Space (EuclideanSpace, ImagePlane), CoordinateSystem[SpaceT] (ReferenceFrame, ImageCoordinateSystem), CoordinateChange[CoordinateSystemT] (inverse, @) with AffineCoordinateChange and RigidCoordinateChange, PlanarPoint[CoordinateSystemT, CoordinateT].

Done
- Pushed 1dfecdfc1c; 29 krrspatial tests pass; #526 and #524 merged it.

Next
- Read CI. Promote after #528, before #526/#524.

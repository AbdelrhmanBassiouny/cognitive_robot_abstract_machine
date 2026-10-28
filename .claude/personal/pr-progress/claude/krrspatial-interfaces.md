PR #527 (user-marked ready, base main): krrspatial's casadi-free base. Plan: domain-models, item planar-point-interface.

Plan
- Space (EuclideanSpace), CoordinateSystem[SpaceT] (ReferenceFrame), CoordinateRepresentation[CoordinateSystemT] (PlanarPoint is one), CoordinateChange[CoordinateSystemT] (inverse, @) with AffineCoordinateChange and RigidCoordinateChange. Image spaces are krrimage's.

Done
- Review: ImagePlane and ImageCoordinateSystem moved to krrimage (5af267fe; #524 a4e9bbdb, #526 ba5d3f3e restacked). 24 krrspatial tests pass on a scalable-plane mimic.
- IdentifiedObject keeps public id and name (owner's call); answered on its thread, left open.

Next
- Read CI on 5af267fe. Owner resolves the IdentifiedObject thread. Promote before #526/#524.

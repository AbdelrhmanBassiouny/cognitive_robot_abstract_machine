PR #527 (ready, base main; #537 landed as cram2#835): krrood_spatial_math's casadi-free base plus SemDT's spatial types adopting it. Plan: domain-models, item planar-point-interface (took over spatial-math-adopt). Decisions: https://claude.ai/artifact/SCiXWvLcV7mequpATSTrsS

Plan
- Space > EuclideanSpace (dimension) > EuclideanSpace2D/3D; CoordinateSystem[SpaceT] > AffineFrame > CartesianFrame > CartesianFrame3D; CoordinateRepresentation (AffinePoint2D, ValueInCartesianFrame3D); CoordinateChange > AffineCoordinateChange[AffineFrameT] > RigidCoordinateChange[CartesianFrameT]. Image spaces are krrood_image's (#524).

Done
- Base interfaces, krrood HasID/HasName, Interface attribute check at definition; all #527 review threads resolved.
- 2026-11-02: reparented onto main, merged main (ae46737a). Re-applied #526's adoption (d5e65ab2): ValueInCartesianFrame3D is a CoordinateRepresentation[CartesianFrame3D] mixin on every spatial value; SpatialType stays the shared base (ORM, renderers, giskardpy read it) but is no value; HomogeneousTransformationMatrix only a RigidCoordinateChange; Point2 an AffinePoint2D[CartesianFrame3D, sm.Scalar]; translation_matrix removed. 76 + 352 tests pass locally (3 mini_world tests need ROS).
- be09c350: CoordinateSystem binds HasName[NameT] with SubClassSafeGeneric; frames carry NameT.
- #526 threads answered (open ones carried by spatial-action, world-as-euclidean-space, the point item, Simon's Q2); #526 closed.

Next
- Your call on the open #527 threads: rename SpatialType (SymbolicSpatialType? here or spatial-math-imports); drop Point here or in planar-coordinate-system.
- CI on be09c350 (ORM build, giskardpy, mini_world), then review and promote. #524 conflicts with main and needs its own resolve.

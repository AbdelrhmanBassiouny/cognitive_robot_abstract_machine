PR #527 (ready, not promoted, base main; #537 landed as cram2#835): krrood_spatial_math's casadi-free base plus SemDT's spatial types adopting it. Plan: domain-models, item planar-point-interface. Decisions: https://claude.ai/artifact/SCiXWvLcV7mequpATSTrsS

Plan
- Space > EuclideanSpace (dimension) > EuclideanSpace2D/3D; CoordinateSystem[SpaceT, NameT] > AffineFrame > CartesianFrame > CartesianFrame3D; CoordinateRepresentation (AffinePoint2D/3D, ValueInCartesianFrame3D); CoordinateChange > AffineCoordinateChange > RigidCoordinateChange. Image spaces are krrood_image's (#524).

Done
- Base interfaces, krrood HasID/HasName, Interface attribute check at definition; #526's adoption re-applied (d5e65ab2, f86b854c); #526 closed.
- 2026-11-10: merged main 20c49dd4 (fc22b482). Conflict only in spatial_types.py with main's new Twist: Twist names ValueInCartesianFrame3D itself, since SpatialType is no value here. 93 krrood_spatial_math + 175 krrood pattern tests pass locally.
- CI on 5c563855: coraplex and physics_simulators red from the runner running out of disk in uv install, not this PR; other test jobs green.

Next
- Read CI on fc22b482.
- Two threads stay open by decision: SymbolicSpatialType rename (spatial-math-imports); dropping Point (planar-coordinate-system).
- Ask the owner whether it is finished before promoting.
- Stacked #549 and #524 conflict with main's changes on restack onto fc22b482; each needs its own resolve.

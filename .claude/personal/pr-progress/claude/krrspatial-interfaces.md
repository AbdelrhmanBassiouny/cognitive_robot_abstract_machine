Plan (2026-11-12 review, decided with owner):
- SpatialChange -> SymbolicSpatialChange; SymbolicSpatialValue (+ planar) replaces ValueInCartesianFrame3D/ValueOnFramePlane
- Operands -> SpecialEuclideanGroupAction / SpecialOrthogonalGroupAction / PlanarSpecialEuclideanGroupAction; MatrixProductAction -> HomogeneousCoordinates; Quaternion/AxisAngle share Orientation
- OrthogonalProjection: abstract plane_normal + foot_point, template projection_line/unproject
- AffinePoint/AffineVector/AffineLine -> Point/Vector/Line; norm/dot/distance on CartesianFrame
- SpaceMap stays points-only (reply on thread)
- 2D/3D -> 2Dimensional/3Dimensional on spatial-math names only (classes, modules, methods, fields, mappings)
Done:
- main de8c8320 merged (b95b26153); 6 conflicts resolved
Next:
- implement the plan above, tests, push via maintenance push, reply inline per thread, update PR description and plan

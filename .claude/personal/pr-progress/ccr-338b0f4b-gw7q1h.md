PR #537 (draft, base claude/krrspatial-interfaces = #527), plan domain-models item spatial-math-move.

Plan:
- Move SemDT spatial_types.py to krrood_spatial_math.spatial_types behind [casadi]; old module re-exports.
- Only changes the move forces: frames typed CartesianFrame3D, CartesianFrame3DReference, exceptions to krrood_spatial_math.exceptions, `_world.transform` -> CartesianFrame3D.express; SemDT entities implement HasName/HasID/CartesianFrame3D, tracker implements CartesianFrame3DResolver.
- Left for the adopt PR (#526 re-applied): CoordinateRepresentation/RigidCoordinateChange/AffinePoint2D on spatial types, docstring rewrites.

Done:
- Branch, draft PR, manifest recorded.

Next:
- Failing tests, then the move, then test runs and push.

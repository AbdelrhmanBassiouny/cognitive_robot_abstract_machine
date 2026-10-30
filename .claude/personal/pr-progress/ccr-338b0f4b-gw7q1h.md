PR #537 (draft, base claude/krrspatial-interfaces = #527), plan domain-models item spatial-math-move.

Plan:
- Move SemDT spatial_types.py to krrood_spatial_math.spatial_types behind [casadi]; old module re-exports.
- Only what the move needs (user asked for minimal): imports, KSE->CartesianFrame3D, CartesianFrame3DReference, express (generic ValueT); KSE is a CartesianFrame3D, tracker a CartesianFrame3DResolver; 2 exceptions moved verbatim.
- Adopt PR (#526 re-applied): CoordinateRepresentation/RigidCoordinateChange/AffinePoint2D, HasName/HasID on WorldEntity, ObjectReference, docstring fixes.

Done:
- Trimmed in 023a7d7c (force-push to rebuild history was refused; squash on merge). PR description current.
- Local: krrood_spatial_math_test 51 pass; SemDT test_spatial_types 373, test_json_parsing 44 (ROS fixtures left to CI).

Next:
- CI on #537; user review; api-break talk with SemDT/krrood code owners.

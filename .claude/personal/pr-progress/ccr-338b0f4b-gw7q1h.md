PR #537 (draft, base claude/krrspatial-interfaces = #527), plan domain-models item spatial-math-move.

Plan:
- Move SemDT spatial_types.py to krrood_spatial_math.spatial_types behind [casadi]; old module re-exports.
- Only what the move needs: CartesianFrame3D frames + reference, express, SpatialType as CoordinateRepresentation, exceptions moved, SemDT entities/tracker implement the interfaces (#526's hunks).
- Adopt PR (#526 re-applied) keeps RigidCoordinateChange, AffinePoint2D, Pose/HTM split, docstring rewrites.

Done:
- Pure-rename commit 67209626, decoupling commit 2eb85829, pushed; PR description + labels api-break, new-feature.
- Local: krrood_spatial_math_test 61 pass; SemDT test_spatial_types 373 pass, test_json_parsing 44 pass (mini_world/cylinder_bot_world fixtures need ROS, left to CI).

Next:
- CI on #537; user review; api-break talk with SemDT/krrood code owners.
- Then spatial-math-adopt re-applies #526 on this branch.

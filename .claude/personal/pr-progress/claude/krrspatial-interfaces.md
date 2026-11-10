PR #527 (ready, not promoted, base main): krrood_spatial_math's casadi-free base, SemDT's spatial types adopting it, and the folded items planar-coordinate-system (#549, closed), spatial-math-imports, projection-interface, spatial-action, frame-checked-arithmetic. Plan: domain-models, item planar-point-interface.

Plan
- Space > EuclideanSpace2D/3D; CoordinateSystem > AffineFrame > CartesianFrame > CartesianFrame2D/3D; AffinePoint[frame, coordinate, vector] > CartesianPoint; AffineVector > CartesianVector; AffineLine; CoordinateChange > Affine > Rigid; SpaceMap > OrthogonalProjection (FramePlaneProjection).

Done
- 32bcb2a3 pushed: 2026-11-10 review implemented (no AffinePoint2D/3D, AffineVector/CartesianVector, Vector2D, AffineLine, OrthogonalProjection interface, FramePlane/PlanarFrame/ValueOnFramePlane, generic SpatialChange); main ecc91acd (keyword-only #923) merged, merge-probe clean. 6 threads resolved; PR description and plan updated; bug-fix label added.

Next
- Read CI on 32bcb2a3 (giskardpy, coraplex, experiments sage10k timeout).
- Open thread: keep the name ValueInCartesianFrame3D? Old open thread: CartesianPoint2D/Pose2D.transform across planes.
- #524 needs its own resolve (PlanarPoint -> AffinePoint with vector type); decisions doc SCiXWvLcV7mequpATSTrsS unreachable.

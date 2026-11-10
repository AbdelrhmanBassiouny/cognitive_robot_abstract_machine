PR #527 (ready, not promoted, base main): krrood_spatial_math's casadi-free base, SemDT's spatial types adopting it, and the folded items planar-coordinate-system (#549, closed), spatial-math-imports, projection-interface, spatial-action, frame-checked-arithmetic. Plan: domain-models, item planar-point-interface.

Plan
- Space > EuclideanSpace2D/3D; CoordinateSystem > AffineFrame > CartesianFrame > CartesianFrame2D/3D; AffinePoint > CartesianPoint; CoordinateChange > Affine > Rigid; SpaceMap (OrthogonalProjection); transforms and point/vector arithmetic check frames.

Done
- 02cc477b pushed: main 6fa88b10 merged; ROS geometry_msgs Pose/Vector3 aliases restored (CI ImportErrors); OmniDrive.origin expresses a framed origin in its parent (coraplex frame mismatches); SpaceMap points bound to AffinePoint, renamed SourcePointT/TargetPointT.
- Review 2026-11-10: replied inline on all 7 threads, all left open for the owner: SpatialChange naming, XY* renames, drop AffinePoint2D/3D, AffineVector, OrthogonalProjection interface, ProjectionLineT bound. Old Point thread resolved.

Next
- Read CI on 02cc477b. experiments sage10k entry point timed out (120 s) on c409fd69 and is not checked locally (its ORM won't build here).
- Implement whichever review proposals the owner accepts; open thread: CartesianPoint2D/Pose2D.transform across planes.
- #524 needs its own resolve; decisions doc SCiXWvLcV7mequpATSTrsS unreachable: record decisions there.

PR #527 (ready, not promoted, base main): krrood_spatial_math's casadi-free base, SemDT's spatial types adopting it, and since 2026-11-10 the folded items planar-coordinate-system (#549, closed), spatial-math-imports, projection-interface, spatial-action, frame-checked-arithmetic. Plan: domain-models, item planar-point-interface.

Plan
- Space > EuclideanSpace2D/3D; CoordinateSystem > AffineFrame > CartesianFrame > CartesianFrame2D/3D; AffinePoint > CartesianPoint; CoordinateChange > Affine > Rigid; SpaceMap (OrthogonalProjection); values implement TransformationOperand, RotationOperand, PlanarTransformationOperand; transforms and point/vector arithmetic check frames.

Done
- c409fd69 pushed: main fd82cbc6 merged, #549 folded (59ab32ef), dimension renames (3179534f), SpaceMap (c29899d7), action and frame checks (c409fd69). Q1/Q4/Q5 decided yes by the owner. Local: 558 spatial tests pass; full SemDT 2227 pass, every failure a missing ROS/robot description.
- PR description and plan updated.

Next
- Read CI on c409fd69, giskardpy above all (mixed-frame arithmetic now raises).
- Open thread: CartesianPoint2D/Pose2D.transform across planes (owner).
- Ask the owner whether it is finished before promoting; #524 stacked on it needs its own resolve.
- Decisions doc SCiXWvLcV7mequpATSTrsS was unreachable from this session: record the fold decisions there.

Plan:
- Planar frames and SE(2) (b04dbd4f8d); AffinePoint/CartesianPoint interfaces; Point2/3 renamed CartesianPoint2D/3D
- CartesianPoint fields stored through abstract CartesianPointMapping; floor-plan panels project via OrthogonalProjection
Done:
- All of the plan, in 5d79553f50 (merges main, #550 and #551)
Next:
- Read CI on #549; #550 and #551 must land first
- Owner: should CartesianPoint2D/Pose2D.transform refuse frames on other planes?

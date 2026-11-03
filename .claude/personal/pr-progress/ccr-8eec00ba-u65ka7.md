Plan:
- CartesianFrame2D interface (base); XYPlane2D, XYPlaneFrame2D, HomogeneousTransformationMatrix2D (casadi)
- Point2/Pose2D given in the plane frame; Pose2D.from_pose by atan2(r21, r11), raising XAxisNormalToPlaneError
- Remove abstract Point; SemDT callers take Point2 | Point3
Done:
- Bootstrap, draft PR #549 on claude/krrspatial-interfaces
Next:
- Tests first in test/krrood_spatial_math_test, then implement

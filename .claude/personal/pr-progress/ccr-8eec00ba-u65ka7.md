Plan:
- CartesianFrame2D (base); XYPlane2D, XYPlaneFrame2D, HomogeneousTransformationMatrix2D (casadi)
- Point2/Pose2D given in the plane frame; Pose2D.from_pose by atan2(r21, r11)
- Remove abstract Point; SemDT callers take Point2 | Point3
Done:
- All of the plan, in b04dbd4f8d; krrood_spatial_math, SemDT spatial-type and geometry tests pass locally
Next:
- Read CI on b04dbd4f8d (ORM build, graph-of-convex-sets and root-conftest tests were not run locally)
- Owner: should Point2/Pose2D.transform refuse frames on other planes?

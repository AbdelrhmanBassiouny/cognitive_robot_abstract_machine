Plan:
- CartesianFrame2D (base); XYPlane2D, XYPlaneFrame2D, HomogeneousTransformationMatrix2D (casadi)
- Point2/Pose2D given in the plane frame; Pose2D.from_pose by atan2(r21, r11)
- Remove abstract Point; SemDT callers take Point2 | Point3
Done:
- All of the plan, in b04dbd4f8d
Next:
- CI red: SemDT ORM build. ORMatic names a DAO after the union bound of PointT, drops the 7 Point2 | Point3 fields, and misses the krrood_spatial_math import
- Owner chose a krrood ORMatic bug-fix PR off main; first settle whether Point2 and Point3 should share an affine-point interface
- Owner: should Point2/Pose2D.transform refuse frames on other planes?

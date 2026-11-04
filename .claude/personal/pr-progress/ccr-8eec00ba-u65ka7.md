Plan:
- Planar frames and SE(2) (b04dbd4f8d); AffinePoint/CartesianPoint interfaces; Point2/3 renamed CartesianPoint2D/3D
- CartesianPoint fields stored through abstract CartesianPointMapping; floor-plan panels project via OrthogonalProjection
Done:
- All of the plan, in 5d79553f50 (merges main, #550 and #551)
- #550 and #551 merged (upstream as cram2#858, cram2#864); fork main is current with cram2 main
- 6228e0805a: merged restacked #527 (now carrying main); migrated Point3 -> CartesianPoint3D in giskardpy tests main added (test_constraint_builders, test_json_parsing, test_cartesian_tasks); clean against base 5c5638552a
- CI at 5d79553f50: only krrood failed, while installing deps (runner out of disk: nvidia-cusparse), not a test failure
Next:
- Read CI on #549 at 6228e0805a (SemDT ORM and ROS-dependent tests can't run in a cloud container)
- Owner: should CartesianPoint2D/Pose2D.transform refuse frames on other planes?

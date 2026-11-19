Plan
- Answer cram2#1019's changes-requested review; the owner posts the replies below.

Done
- c9ac60d8 merges main b691f5af; probe clean. 3fc103c0: EmbeddedPlanes equal when coplanar (compare_xy_plane); SE(2) constructor refuses frames on two planes or mirrored.

Next
- Owner: post the replies below; read CI on 3fc103c0; discuss the fork's MetricPoint/Vector naming thread.
- #524: restack conflicts in its own files (ci.yml, pyproject files, conftest, test_orm, version test); needs its own resolve.

Replies for cram2#1019
- Review: Worth it, and a real inconsistency: the plan says two planes are equal when they share a space and their points, but EmbeddedPlane compared frames. Fixed in 3fc103c0: CartesianFrame3Dimensional.compare_xy_plane gives an XYPlaneRelation, and EmbeddedPlane equality uses it, so floor and robot_base span one plane and SE(2) between them stays in it.
- :3624: Yes. In 3fc103c0 the constructor checks both frames when given, so from_xy_yaw, inverse() and @ raise FramesOnDifferentPlanesError or MirroredPlaneFramesError too.
- :3665: The check now lives once in _ensure_rigid_change_on_one_plane, called by the constructor and from_transformation; it is the plane counterpart of _ensure_consistent_frame, kept separate because one wants one frame and the other two frames on one plane facing one side.

Plan
- Answer cram2#1019's reviews; the owner posts the replies below.

Done
- c9ac60d8 merges main b691f5af; probe clean. 3fc103c0: coplanar EmbeddedPlanes equal; SE(2) constructor refuses frames on two planes or mirrored. 4a54dac8 + 9c624d9e: renamed to EmbeddedPlaneRelation, compare_embedded_plane(_in_own_space), embedded_plane_relation. 5fe60be8: casadi-free LineSegment whose line runs start→end; Line.point_at_position; AxialGrasp uses it.

Next
- Owner: post the replies below; read CI on 5fe60be8; discuss the fork's MetricPoint/Vector thread.
- #524: restack conflicts in its own files; needs its own resolve.

Replies for cram2#1019
- Review: a real inconsistency. Fixed in 3fc103c0: EmbeddedPlane equality uses CartesianFrame3Dimensional.compare_embedded_plane (EmbeddedPlaneRelation), so floor and robot_base span one plane and SE(2) between them stays in it.
- :3727: In 3fc103c0 the constructor checks both frames, so from_xy_yaw, inverse() and @ raise FramesOnDifferentPlanesError or MirroredPlaneFramesError too.
- :3665: The check lives once in _ensure_rigid_change_on_one_plane (constructor and from_transformation); kept apart from _ensure_consistent_frame, which checks one frame, not two on one plane.
- cartesian_frame_3_dimensional :34/:116/:131: renamed in 4a54dac8.
- :2366: Yes; 5fe60be8 makes LineSegment3Dimensional a LineSegment whose line passes through start along end − start (Line3Dimensional), with Line.point_at_position. Used only by HasGraspCandidates.grasp_axis; AxialGrasp now takes its point from axis.line.

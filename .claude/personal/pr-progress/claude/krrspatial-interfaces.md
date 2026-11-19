Plan
- Answer cram2#1019's reviews; the owner posts the replies below.

Done
- c9ac60d8 merges main b691f5af; probe clean. 3fc103c0: coplanar EmbeddedPlanes equal; SE(2) constructor refuses frames on two planes or mirrored. 4a54dac8 + 9c624d9e: renamed to EmbeddedPlaneRelation, compare_embedded_plane(_in_own_space), embedded_plane_relation.

Next
- Owner: post the replies below; read CI on 9c624d9e; discuss the fork's MetricPoint/Vector thread.
- #524: restack conflicts in its own files; needs its own resolve.

Replies for cram2#1019
- Review: a real inconsistency. Fixed in 3fc103c0: EmbeddedPlane equality uses CartesianFrame3Dimensional.compare_embedded_plane (EmbeddedPlaneRelation), so floor and robot_base span one plane and SE(2) between them stays in it.
- :3727: In 3fc103c0 the constructor checks both frames, so from_xy_yaw, inverse() and @ raise FramesOnDifferentPlanesError or MirroredPlaneFramesError too.
- :3665: The check lives once in _ensure_rigid_change_on_one_plane (constructor and from_transformation); kept apart from _ensure_consistent_frame, which checks one frame, not two on one plane.
- cartesian_frame_3_dimensional :34/:116/:131: renamed in 4a54dac8.
- :2366: LineSegment3Dimensional came from main (a61695e); only HasGraspCandidates.grasp_axis and axial grasping use it, and nothing needs it as a Line3Dimensional yet, so no conversion was added.

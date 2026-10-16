"""Probe helper: replace an object's grasps by grasps from above."""
import numpy as np

from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.spatial_types.spatial_types import Point3, Pose, RotationMatrix, Vector3


def use_top_grasps(graspable, finger_axis_count=4, depth_below_top=0.03):
    body = graspable.root
    box = body.collision.as_bounding_box_collection_in_frame(body).bounding_box()
    center_z = (box.z_interval.lower + box.z_interval.upper) / 2
    position = Point3(
        (box.x_interval.lower + box.x_interval.upper) / 2,
        (box.y_interval.lower + box.y_interval.upper) / 2,
        max(center_z, box.z_interval.upper - depth_below_top),
        reference_frame=body,
    )
    grasps = [
        GraspCandidate(
            graspable,
            Pose(
                position=position,
                orientation=RotationMatrix.from_vectors(
                    x=Vector3.NEGATIVE_Z(), y=Vector3(np.cos(angle), np.sin(angle), 0.0)
                ).quaternion,
                reference_frame=body,
            ),
        )
        for angle in np.linspace(0, np.pi, finger_axis_count, endpoint=False)
    ]
    graspable.grasp_candidates = lambda: grasps
    return grasps

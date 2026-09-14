"""
The camera Tracy's description carries: where it hangs on the robot, which way it looks
and how wide it sees, so a simulated picture is taken from where the real one is.
"""

from __future__ import annotations

import numpy as np
from semantic_digital_twin.adapters.multi_sim import MujocoCamera
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world import World
from typing_extensions import Optional

from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.simulated_camera import CAMERA_T_OPTICAL
from experiments.montessori.perception.simulated_setup import (
    CAMERA_FIELD_OF_VIEW,
    CAMERA_PICTURE_HEIGHT,
    CAMERA_PICTURE_WIDTH,
)
from experiments.tracy_experiments.equipment import TRACY_MOUNT_ROOT_NAME

# %% where the camera stands on the description

CAMERA_NAME = "tracy_camera"
"""
What the simulated camera is called.
"""

CAMERA_LINK_NAME = "camera_link"
"""
The body of Tracy's description the camera hangs on.
"""

CAMERA_CALIBRATION_CAPTURE = "tracy_pickup_demo"
"""
The capture whose record of where the camera stood the simulated camera is stood by.

All eight shipped captures agree on that pose to a ten-millionth of a metre, so any one
of them says it; this is the one taken of the run the simulated demo stands in for.
"""


def camera_link_T_optical(world: World) -> np.ndarray:
    """
    Where the colour camera's optical frame stands on the ``camera_link`` of the
    description ``world`` was built from.

    A capture records where the camera stood in Tracy's own frame, which is the same
    wherever ``camera_link`` is said to be; how far the optical frame lies from that
    link is what differs between one calibration of the description and the next, so it
    is worked out against the description at hand rather than stated.

    :param world: The world holding Tracy.
    :return: The offset as a 4x4 homogeneous transformation.
    """
    tracy_root = world.get_body_by_name(TRACY_MOUNT_ROOT_NAME)
    camera_link = world.get_body_by_name(CAMERA_LINK_NAME)
    root_T_link = world.compute_forward_kinematics_np(tracy_root, camera_link)
    root_T_optical = SceneCapture.load(
        CAMERA_CALIBRATION_CAPTURE
    ).reference_frame_T_camera
    return np.linalg.inv(root_T_link) @ root_T_optical


# %% hanging it on a world


def tracys_camera(world: World) -> MujocoCamera:
    """
    The camera as it stands on Tracy's ``camera_link`` in the given world, where the
    real one stands, looking the way it looks and seeing as wide as it sees; not hung on
    the world yet.

    :param world: The world holding Tracy.
    """
    link_T_camera = camera_link_T_optical(world) @ np.linalg.inv(CAMERA_T_OPTICAL)
    x, y, z, real = (
        HomogeneousTransformationMatrix(link_T_camera).to_quaternion().to_np().tolist()
    )
    return MujocoCamera(
        name=CAMERA_NAME,
        body=world.get_body_by_name(CAMERA_LINK_NAME),
        position=link_T_camera[:3, 3].tolist(),
        quaternion=[real, x, y, z],
        fovy=CAMERA_FIELD_OF_VIEW,
        resolution=[float(CAMERA_PICTURE_WIDTH), float(CAMERA_PICTURE_HEIGHT)],
    )


def camera_on_tracy(world: World) -> MujocoCamera:
    """
    Hang the camera on Tracy's ``camera_link``.

    :param world: The world holding Tracy.
    :return: The camera, attached to the link.
    """
    camera = tracys_camera(world)
    camera.body.simulator_additional_properties.append(camera)
    return camera


def camera_of_the_robot(world: World) -> Optional[MujocoCamera]:
    """
    The camera the robot of the given world looks through, not hung on the world yet, or
    None where the world holds no robot with a camera of its own.

    :param world: The world to read.
    """
    if not world.get_semantic_annotations_by_type(Tracy):
        return None
    return tracys_camera(world)

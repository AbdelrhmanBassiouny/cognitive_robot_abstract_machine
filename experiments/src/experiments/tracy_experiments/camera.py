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

from experiments.montessori.perception.simulated_camera import CAMERA_T_OPTICAL
from experiments.montessori.perception.simulated_setup import (
    CAMERA_FIELD_OF_VIEW,
    CAMERA_PICTURE_HEIGHT,
    CAMERA_PICTURE_WIDTH,
)

# %% where the camera stands on the description

CAMERA_NAME = "tracy_camera"
"""
What the simulated camera is called.
"""

CAMERA_LINK_NAME = "camera_link"
"""
The body of Tracy's description the camera hangs on.
"""

CAMERA_LINK_T_OPTICAL = HomogeneousTransformationMatrix.from_xyz_rpy(
    x=0.041737,
    y=-0.014025,
    z=0.009141,
    roll=-1.363448,
    pitch=0.003959,
    yaw=-1.546731,
).to_np()
"""
Where the colour camera's optical frame stands on the ``camera_link`` a scene is built
on.

Read off the shipped captures, which agree on it to a ten-millionth of a metre. It is
not the plain quarter turns a description states between a camera link and its optical
frame: the lab calibrates the camera in the description in Tracy's own ROS workspace,
not in the published one a scene is built from, and this pose carries the difference
between the two so that the simulated camera looks where the real one looked.
"""


# %% hanging it on a world


def tracys_camera(world: World) -> MujocoCamera:
    """
    The camera as it stands on Tracy's ``camera_link`` in the given world, where the
    real one stands, looking the way it looks and seeing as wide as it sees; not hung
    on the world yet.

    :param world: The world holding Tracy.
    """
    link_T_camera = CAMERA_LINK_T_OPTICAL @ np.linalg.inv(CAMERA_T_OPTICAL)
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
    The camera the robot of the given world looks through, not hung on the world yet,
    or None where the world holds no robot with a camera of its own.

    :param world: The world to read.
    """
    if not world.get_semantic_annotations_by_type(Tracy):
        return None
    return tracys_camera(world)

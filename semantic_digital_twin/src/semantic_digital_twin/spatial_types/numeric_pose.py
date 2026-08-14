"""
A pose held as plain numbers, and the conversion that reads one out of a transform.

The spatial types are CasADi-backed: reading one evaluates an expression graph whose
nodes are reference counted without atomics, while CasADi releases the GIL for the
duration of a call. Poses that are read for display, for recording, or from any thread
other than the one that owns the world therefore have to be read out into numbers first,
without building any symbolic expression on the way.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from typing_extensions import List, Tuple, TYPE_CHECKING

from semantic_digital_twin.datastructures.types import NpMatrix4x4

if TYPE_CHECKING:
    from semantic_digital_twin.spatial_types.spatial_types import Pose


@dataclass(frozen=True)
class NumericPose:
    """
    A pose read out into plain numbers, holding nothing symbolic.

    ..warning:: Read one out on the thread that owns the world, and hand only the
       result to any other thread.
    """

    position: Tuple[float, float, float]
    """
    The pose's x, y and z coordinates.
    """

    quaternion: Tuple[float, float, float, float]
    """
    The pose's orientation, as x, y, z and w.
    """

    @classmethod
    def from_transformation_matrix(cls, root_T_body: NpMatrix4x4) -> NumericPose:
        """
        Read a transformation matrix out as a position and a quaternion.

        :param root_T_body: The transform to read out.
        """
        return cls(
            position=(
                float(root_T_body[0, 3]),
                float(root_T_body[1, 3]),
                float(root_T_body[2, 3]),
            ),
            quaternion=cls._quaternion_of(root_T_body),
        )

    @classmethod
    def of_pose(cls, pose: Pose) -> NumericPose:
        """
        Read a pose out into plain numbers.

        :param pose: The pose to read out.
        """
        return cls.from_transformation_matrix(pose.to_np())

    @staticmethod
    def _quaternion_of(
        root_T_body: NpMatrix4x4,
    ) -> Tuple[float, float, float, float]:
        """
        The orientation of a transform as a quaternion, as x, y, z and w.

        Picks the largest diagonal entry to divide by, so a half turn -- whose trace
        leaves the direct formula dividing by nearly zero -- stays accurate.

        :param root_T_body: The transform whose orientation is converted.
        """
        homogeneous_scale = root_T_body[3, 3]
        trace = (
            root_T_body[0, 0]
            + root_T_body[1, 1]
            + root_T_body[2, 2]
            + homogeneous_scale
        )
        if trace - homogeneous_scale > 0:
            components = [
                root_T_body[2, 1] - root_T_body[1, 2],
                root_T_body[0, 2] - root_T_body[2, 0],
                root_T_body[1, 0] - root_T_body[0, 1],
                trace,
            ]
            return NumericPose._scaled(components, trace, homogeneous_scale)

        largest = int(np.argmax(np.diagonal(root_T_body)[:3]))
        following = (largest + 1) % 3
        preceding = (largest + 2) % 3
        diagonal_difference = (
            root_T_body[largest, largest]
            - (root_T_body[following, following] + root_T_body[preceding, preceding])
            + homogeneous_scale
        )
        components = [0.0, 0.0, 0.0, 0.0]
        components[largest] = diagonal_difference
        components[following] = (
            root_T_body[largest, following] + root_T_body[following, largest]
        )
        components[preceding] = (
            root_T_body[preceding, largest] + root_T_body[largest, preceding]
        )
        components[3] = (
            root_T_body[preceding, following] - root_T_body[following, preceding]
        )
        return NumericPose._scaled(components, diagonal_difference, homogeneous_scale)

    @staticmethod
    def _scaled(
        components: List[float], divisor: float, homogeneous_scale: float
    ) -> Tuple[float, float, float, float]:
        """
        Normalise the components a branch of the conversion produced.

        :param components: The unnormalised x, y, z and w components.
        :param divisor: The quantity the branch built its components from.
        :param homogeneous_scale: The transform's bottom right entry.
        """
        scale = 0.5 / math.sqrt(divisor * homogeneous_scale)
        return (
            float(components[0] * scale),
            float(components[1] * scale),
            float(components[2] * scale),
            float(components[3] * scale),
        )

    def to_position_quaternion_list(self) -> List[float]:
        """
        :return: This pose's position and orientation, as ``[x, y, z, qx, qy, qz, qw]``.
        """
        return [*self.position, *self.quaternion]

    @property
    def label(self) -> str:
        """
        The pose formatted for display, to two decimal places.
        """
        return "(%.2f, %.2f, %.2f) q(%.2f, %.2f, %.2f, %.2f)" % (
            *self.position,
            *self.quaternion,
        )

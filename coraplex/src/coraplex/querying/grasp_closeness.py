from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from typing_extensions import Iterable, Iterator

from krrood.entity_query_language.predicate import RenderedFields, SymbolicFunction
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    FunctionVerbalizationTemplates,
)
from semantic_digital_twin.grasping.grasp_candidates import (
    GraspCandidate,
    HasGraspCandidates,
)
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types.spatial_types import Pose

# %% how close a grasp is to where the robot stands


@dataclass(frozen=True, order=True)
class GraspCloseness:
    """
    How close a grasp is to where the robot stands: a grasp nearer by horizontal
    distance is closer, and of two equally near grasps the one approached more directly
    from the standing position is.
    """

    horizontal_distance: float
    """
    The horizontal distance from the standing position to the grasp, in meters.
    """

    approach_angle: float
    """
    The angle between the direction the grasp is approached along and the direction from
    the standing position to it, in radians.
    """

    @classmethod
    def of(
        cls,
        grasp: GraspCandidate,
        world_T_object: NDArray[np.float64],
        world_P_standing: NDArray[np.float64],
    ) -> GraspCloseness:
        """
        :param grasp: A grasp on the object.
        :param world_T_object: The object's root frame in the world frame.
        :param world_P_standing: Where the robot stands, as a homogeneous point in the
            world frame.
        :return: How close `grasp` is to the standing position.
        """
        world_T_grasp = world_T_object @ grasp.grasp_pose.to_np()
        world_V_standing_to_grasp = world_T_grasp[:, 3] - world_P_standing
        horizontal_distance = float(np.linalg.norm(world_V_standing_to_grasp[:2]))
        distance = np.linalg.norm(world_V_standing_to_grasp)
        if distance == 0:
            # Standing exactly at the grasp leaves no direction to approach it from.
            return cls(horizontal_distance, 0.0)
        cosine = world_T_grasp[:, 0] @ world_V_standing_to_grasp / distance
        return cls(horizontal_distance, float(np.arccos(np.clip(cosine, -1.0, 1.0))))

    @classmethod
    def ranked(
        cls, graspable: HasGraspCandidates, world_P_standing: NDArray[np.float64]
    ) -> list[GraspCandidate]:
        """
        :param graspable: The object offering the grasps.
        :param world_P_standing: Where the robot stands, as a homogeneous point in the
            world frame.
        :return: The grasps `graspable` offers, the closest to the standing position
            first.
        """
        world_T_object = graspable.root.global_transform.to_np()
        return sorted(
            graspable.grasp_candidates(),
            key=lambda grasp: cls.of(grasp, world_T_object, world_P_standing),
        )


# %% the grasps of an object closest to a standing position


@dataclass(eq=False)
class ClosestGrasps(SymbolicFunction):
    """
    The grasps an object offers that are closest to a standing position by their
    :class:`GraspCloseness`, the closest first.
    """

    graspable: HasGraspCandidates
    """
    The object offering the grasps.
    """

    standing_position: Pose
    """
    Where the robot stands while taking one of the grasps.
    """

    number_of_grasps: int = 3
    """
    How many of the closest grasps are kept.
    """

    def __call__(self) -> list[GraspCandidate]:
        world = self.graspable.root._world
        world_P_standing = world.transform(self.standing_position, world.root).to_np()[
            :, 3
        ]
        return GraspCloseness.ranked(self.graspable, world_P_standing)[
            : self.number_of_grasps
        ]

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        :param fields: The rendered fragment for each field.
        :return: The noun phrase *"the closest grasps of <graspable> and <standing
            position>"*.
        """
        return FunctionVerbalizationTemplates.possessive(
            cls, fields["graspable"], fields["standing_position"]
        )


# %% the grasps of an object, closest to the robot first


@dataclass
class GraspsClosestToTheRobot(Iterable[GraspCandidate]):
    """
    The grasps an object offers, ordered by their :class:`GraspCloseness` to where the
    robot stands when they are iterated.
    """

    graspable: HasGraspCandidates
    """
    The object offering the grasps.
    """

    robot: AbstractRobot
    """
    The robot taking one of the grasps.
    """

    def __iter__(self) -> Iterator[GraspCandidate]:
        """
        :return: The grasps of :attr:`graspable`, the closest to :attr:`robot` first.

        .. warning::
            Must stay a generator, so the robot's position is read at the first ``next``
            rather than while the plan is built. EQL's ``variable`` calls :func:`iter`
            on its domain while the plan is built.
        """
        yield from GraspCloseness.ranked(
            self.graspable, self.robot.root.global_transform.to_np()[:, 3]
        )

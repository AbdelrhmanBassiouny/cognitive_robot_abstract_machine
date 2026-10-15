"""
Tasks moving the base a drive carries, relative to the parent of that drive.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import krrood.symbolic_math.symbolic_math as sm
from cramph.context import StatechartContext
from giskardpy.motion_statechart.graph_node import ConvergingTask, MotionNodeArtifacts
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianOrientation,
    CartesianPosition,
)
from semantic_digital_twin.spatial_types import (
    HomogeneousTransformationMatrix,
    RotationMatrix,
    Vector3,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

# %% moving a driven base


@dataclass(eq=False, repr=False)
class DrivenBaseTask(ConvergingTask, ABC):
    """
    Moves the base a drive carries towards :attr:`goal_pose`, relative to the parent of
    the drive as it is whenever the task is built.

    A base moved under another parent while the statechart runs is therefore driven
    relative to that parent, and the joints above the drive are never moved for it.
    """

    base: KinematicStructureEntity = field(kw_only=True)
    """
    The body the drive carries.
    """

    goal_pose: Pose = field(kw_only=True)
    """
    Where the base should end up.
    """

    parent_T_goal_reference_frame: HomogeneousTransformationMatrix = field(kw_only=True)
    """
    The pose of the reference frame of :attr:`goal_pose` relative to the parent of the
    drive, as the goal running this task fixed it.
    """

    @property
    def drive_parent(self) -> KinematicStructureEntity:
        """
        :return: The body the drive carrying :attr:`base` is attached to now.
        """
        return self.base.parent_kinematic_structure_entity

    @property
    def parent_T_goal(self) -> Pose:
        """
        :return: :attr:`goal_pose` relative to :attr:`drive_parent`.
        """
        parent_T_goal = self.parent_T_goal_reference_frame @ self.goal_pose
        parent_T_goal.reference_frame = self.drive_parent
        return parent_T_goal

    def parent_T_base(
        self, context: StatechartContext
    ) -> HomogeneousTransformationMatrix:
        """
        :param context: The context this task is built in.
        :return: The pose of :attr:`base` relative to :attr:`drive_parent`, over the
            degrees of freedom of the drive.
        """
        return context.world.compose_forward_kinematics_expression(
            self.drive_parent, self.base
        )


@dataclass(eq=False, repr=False)
class BasePosition(DrivenBaseTask):
    """
    Drives the base to the position of :attr:`goal_pose`.
    """

    reference_velocity: float = field(
        default=CartesianPosition.default_reference_velocity, kw_only=True
    )
    """
    Reference velocity for normalization in m/s.
    """

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        """
        :return: The artifacts of this task, whose error is the distance between the
            base and the goal position.
        """
        artifacts = MotionNodeArtifacts()
        parent_P_goal = self.parent_T_goal.position
        parent_P_base = self.parent_T_base(context).position
        artifacts.geometry.add_point_goal_constraints(
            frame_P_goal=parent_P_goal,
            frame_P_current=parent_P_base,
            reference_velocity=self.reference_velocity,
            quadratic_weight=self.weight,
        )
        artifacts.error = parent_P_goal.euclidean_distance(parent_P_base)
        return artifacts


@dataclass(eq=False, repr=False)
class DrivenBaseRotation(DrivenBaseTask, ABC):
    """
    Turns the base until it has the orientation :meth:`parent_R_goal` describes.
    """

    reference_velocity: float = field(
        default=CartesianOrientation.default_reference_velocity, kw_only=True
    )
    """
    Reference angular velocity for normalization in rad/s.
    """

    @abstractmethod
    def parent_R_goal(
        self, parent_T_base: HomogeneousTransformationMatrix
    ) -> RotationMatrix:
        """
        :param parent_T_base: The pose of the base relative to the drive's parent.
        :return: The orientation the base should have, relative to the drive's parent.
        """

    def build_artifacts(self, context: StatechartContext) -> MotionNodeArtifacts:
        """
        :return: The artifacts of this task, whose error is the angle between the
            orientation of the base and the goal orientation.
        """
        artifacts = MotionNodeArtifacts()
        parent_T_base = self.parent_T_base(context)
        parent_R_goal = self.parent_R_goal(parent_T_base)
        parent_R_base = parent_T_base.rotation_matrix
        artifacts.geometry.add_rotation_goal_constraints(
            frame_R_current=parent_R_base,
            frame_R_goal=parent_R_goal,
            reference_velocity=self.reference_velocity,
            quadratic_weight=self.weight,
        )
        artifacts.error = sm.abs(parent_R_base.rotational_distance(parent_R_goal))
        return artifacts


@dataclass(eq=False, repr=False)
class BaseOrientation(DrivenBaseRotation):
    """
    Turns the base to the orientation of :attr:`goal_pose`.
    """

    def parent_R_goal(
        self, parent_T_base: HomogeneousTransformationMatrix
    ) -> RotationMatrix:
        return self.parent_T_goal.rotation_matrix


@dataclass(eq=False, repr=False)
class BaseHeading(DrivenBaseRotation):
    """
    Turns the front of the base towards the position of :attr:`goal_pose`, from wherever
    the base is.
    """

    def parent_R_goal(
        self, parent_T_base: HomogeneousTransformationMatrix
    ) -> RotationMatrix:
        parent_V_base_to_goal = self.parent_T_goal.position - parent_T_base.position
        parent_V_base_to_goal.scale(1)
        return RotationMatrix.from_vectors(
            x=parent_V_base_to_goal,
            z=Vector3.Z(reference_frame=self.drive_parent),
            reference_frame=self.drive_parent,
        )

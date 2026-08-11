"""
Synthetic robot description used to test that the Montessori demo's robot-handling code
(:class:`~experiments.montessori.world.MontessoriWorld`,
:mod:`experiments.montessori.montessori_demo`) generalizes to robots other than
:class:`~semantic_digital_twin.robots.hsrb.HSRB`, without depending on a second real
robot's ROS package.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Self

from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.robots.robot_part_mixins import HasEndEffector
from semantic_digital_twin.robots.robot_parts import AbstractRobot, EndEffector
from semantic_digital_twin.spatial_types import Quaternion
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

SYNTHETIC_WHEELED_ARM_ROBOT_URDF_PATH = str(
    Path(__file__).with_name("synthetic_wheeled_arm_robot.urdf")
)
"""
Local, self-contained URDF (needs no ROS package to resolve, unlike every other
:class:`~semantic_digital_twin.robots.robot_parts.AbstractRobot` in this codebase)
describing :class:`SyntheticWheeledArmRobot`.
"""


@dataclass(eq=False)
class SyntheticGripper(EndEffector):
    """
    The single end effector of :class:`SyntheticWheeledArmRobot`, at ``gripper_link``.
    """

    def setup_hardware_interfaces(self):
        for joint_name in ("arm_joint", "gripper_joint"):
            self._world.get_connection_by_name(joint_name).has_hardware_interface = True

    def setup_joint_states(self) -> list[JointState]:
        return []

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        world = robot_root._world
        return cls(
            root=world.get_body_in_branch_by_name(robot_root, "arm_link"),
            tool_frame=world.get_body_in_branch_by_name(robot_root, "gripper_link"),
            front_facing_orientation=Quaternion(0, 0, 0, 1),
        )


@dataclass(eq=False)
class SyntheticWheeledArmRobot(AbstractRobot, HasEndEffector[SyntheticGripper]):
    """
    Minimal, self-contained :class:`~semantic_digital_twin.robots.robot_parts.AbstractRobot`
    standing in for "some robot that is not HSRB", to prove that generic robot-handling
    code (e.g.
    :meth:`~experiments.montessori.world.MontessoriWorld.spawn_robot`,
    :func:`~experiments.montessori.montessori_demo._base_connections_without_hardware_interface`)
    is not accidentally specific to :class:`~semantic_digital_twin.robots.hsrb.HSRB`.

    Its description (:data:`SYNTHETIC_WHEELED_ARM_ROBOT_URDF_PATH`) is a small local
    file rather than a real robot's ROS package, so resolving it needs no external
    dependency. ``base_link`` carries two unactuated wheel joints, named unlike any of
    HSRB's own wheel joints, standing in for a mobile base's passive/drive wheels, plus
    one controlled arm joint driving :attr:`end_effector`.
    """

    @classmethod
    def get_ros_file_path(cls) -> str:
        return SYNTHETIC_WHEELED_ARM_ROBOT_URDF_PATH

    @classmethod
    def _get_root_body_name(cls) -> str:
        return "base_link"

    def _setup_collision_rules(self):
        pass

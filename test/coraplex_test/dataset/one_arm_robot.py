"""
A robot with one arm and a gripper, described by a local URDF, so an action that only
needs *some* arm to hold and release a body can be tested without a real robot's ROS
description package.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from typing_extensions import Self

from semantic_digital_twin.datastructures.definitions import (
    GripperState,
    StaticJointState,
)
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.robot_part_mixins import HasOneArm
from semantic_digital_twin.robots.robot_parts import AbstractRobot, Arm, EndEffector
from semantic_digital_twin.spatial_types import Quaternion
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

ONE_ARM_ROBOT_URDF_PATH = str(Path(__file__).with_name("one_arm_robot.urdf"))
"""
The local URDF :class:`OneArmRobot` is parsed from, which resolves without a ROS package
or a network fetch.
"""

GRIPPER_CONNECTION_NAME = "gripper_joint"
"""
The connection driving the gripper's single sliding finger.
"""

ARM_CONNECTION_NAME = "arm_joint"
"""
The connection driving the arm.
"""

GRIPPER_OPENING = 0.05
"""
How far the finger stands from the gripper's root when open, in metres.
"""


@dataclass(eq=False)
class OneArmGripper(EndEffector):
    """
    :class:`OneArmRobot`'s single gripper, at ``gripper_link``.
    """

    def setup_hardware_interfaces(self):
        self._world.get_connection_by_name(
            GRIPPER_CONNECTION_NAME
        ).has_hardware_interface = True

    def setup_joint_states(self) -> list[JointState]:
        # The connection into this gripper's root rather than one within it, so it is
        # referenced by name rather than through active_connections, which spans only
        # the gripper's own chain.
        connection = self._world.get_connection_by_name(GRIPPER_CONNECTION_NAME)
        return [
            JointState.from_mapping(
                name=PrefixedName("gripper_open", prefix=self.name.name),
                mapping={connection: GRIPPER_OPENING},
                state_type=GripperState.OPEN,
            ),
            JointState.from_mapping(
                name=PrefixedName("gripper_close", prefix=self.name.name),
                mapping={connection: 0.0},
                state_type=GripperState.CLOSE,
            ),
        ]

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        gripper_link = robot_root._world.get_body_in_branch_by_name(
            robot_root, "gripper_link"
        )
        return cls(
            root=gripper_link,
            tool_frame=gripper_link,
            front_facing_orientation=Quaternion(0, 0, 0, 1),
        )


@dataclass(eq=False)
class OneArm(Arm[OneArmGripper]):
    """
    :class:`OneArmRobot`'s single arm, from ``base_link`` to ``arm_link``.
    """

    def setup_hardware_interfaces(self):
        self._world.get_connection_by_name(
            ARM_CONNECTION_NAME
        ).has_hardware_interface = True

    def setup_joint_states(self) -> list[JointState]:
        [connection] = self.active_connections
        return [
            JointState.from_mapping(
                name=PrefixedName("arm_park", prefix=self.name.name),
                mapping={connection: 0.0},
                state_type=StaticJointState.PARK,
            )
        ]

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        world = robot_root._world
        return cls(
            root=world.get_body_in_branch_by_name(robot_root, "base_link"),
            tip=world.get_body_in_branch_by_name(robot_root, "arm_link"),
        )


@dataclass(eq=False)
class OneArmRobot(AbstractRobot, HasOneArm[OneArm]):
    """
    A robot that is nothing but one arm with a gripper on it.

    Enough for an action that reads which arm holds a body and which gripper lets it go,
    and no more: every other robot in this workspace is described by a ROS package that
    a checkout without ROS cannot resolve.
    """

    @classmethod
    def get_ros_file_path(cls) -> str:
        return ONE_ARM_ROBOT_URDF_PATH

    @classmethod
    def _get_root_body_name(cls) -> str:
        return "base_link"

    def _setup_collision_rules(self):
        pass

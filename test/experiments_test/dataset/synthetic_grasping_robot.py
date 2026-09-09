"""
Synthetic robot description used to test behaviour that asks whether a robot is holding
something, without depending on a real two-fingered robot's own ROS package.

Unlike
:class:`~test.experiments_test.dataset.synthetic_fixed_arm_robot.SyntheticFixedArmRobot`,
this one carries geometry and a pair of fingers, so
:func:`~semantic_digital_twin.reasoning.robot_predicates.robot_holds_body` -- which
casts rays from one finger tip to the other -- has something to cast between.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from typing_extensions import List, Self

from semantic_digital_twin.datastructures.definitions import (
    GripperState,
    StaticJointState,
)
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.robot_part_mixins import HasOneArm, HasTwoFingers
from semantic_digital_twin.robots.robot_parts import (
    AbstractRobot,
    Arm,
    EndEffector,
    Finger,
)
from semantic_digital_twin.spatial_types import Quaternion
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)

SYNTHETIC_GRASPING_ROBOT_URDF_PATH = str(
    Path(__file__).with_name("synthetic_grasping_robot.urdf")
)
"""
Local, self-contained URDF describing :class:`SyntheticGraspingRobot`, resolvable
without a ROS package or network access.
"""

FINGERS_POINT_DOWN = Quaternion(0, -math.sqrt(0.5), 0, math.sqrt(0.5))
"""
Where the pincer's tool frame points, as the quarter turn about y that takes the
canonical grasp frame's forward axis onto the direction this pincer reaches along.

The fingers hang below the pincer, so a grasp comes down onto a piece; without saying
so, a top grasp would turn the fingers sideways and close them beside it.
"""

FINGER_OPENING = 0.05
"""
How far each finger is asked to travel from the pincer's open position to its closed
one, in metres.

The two fingers start 0.08 m apart, so this asks them to shut past each other -- what a
real gripper is commanded to do when it squeezes, and what leaves the fingers around a
piece rather than beside it once a motion has stopped within its own tolerance of the
position it was given.
"""


@dataclass(eq=False)
class SyntheticLeftFinger(Finger):
    """
    The left finger of :class:`SyntheticPincer`, which stands in for a thumb.
    """

    def setup_hardware_interfaces(self):
        self._world.get_connection_by_name(
            "left_finger_joint"
        ).has_hardware_interface = True

    def setup_joint_states(self) -> List[JointState]:
        return []

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        world = robot_root._world
        return cls(
            root=world.get_body_in_branch_by_name(robot_root, "left_finger_link"),
            tip=world.get_body_in_branch_by_name(robot_root, "left_fingertip_link"),
        )


@dataclass(eq=False)
class SyntheticRightFinger(Finger):
    """
    The right finger of :class:`SyntheticPincer`.
    """

    def setup_hardware_interfaces(self):
        self._world.get_connection_by_name(
            "right_finger_joint"
        ).has_hardware_interface = True

    def setup_joint_states(self) -> List[JointState]:
        return []

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        world = robot_root._world
        return cls(
            root=world.get_body_in_branch_by_name(robot_root, "right_finger_link"),
            tip=world.get_body_in_branch_by_name(robot_root, "right_fingertip_link"),
        )


@dataclass(eq=False)
class SyntheticPincer(
    EndEffector, HasTwoFingers[SyntheticLeftFinger, SyntheticRightFinger]
):
    """
    The two-fingered end effector of :class:`SyntheticGraspingRobot`.
    """

    def setup_hardware_interfaces(self):
        self._setup_hardware_interfaces_for_active_connections()

    def setup_joint_states(self) -> List[JointState]:
        connections = [
            self._world.get_connection_by_name(name)
            for name in ("left_finger_joint", "right_finger_joint")
        ]
        gripper_open = JointState.from_mapping(
            name=PrefixedName("gripper_open", prefix=self.name.name),
            mapping={connection: 0.0 for connection in connections},
            state_type=GripperState.OPEN,
        )
        gripper_close = JointState.from_mapping(
            name=PrefixedName("gripper_close", prefix=self.name.name),
            mapping={connection: FINGER_OPENING for connection in connections},
            state_type=GripperState.CLOSE,
        )
        return [gripper_open, gripper_close]

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        world = robot_root._world
        return cls(
            root=world.get_body_in_branch_by_name(robot_root, "pincer_link"),
            tool_frame=world.get_body_in_branch_by_name(robot_root, "grasp_link"),
            front_facing_orientation=FINGERS_POINT_DOWN,
        )


@dataclass(eq=False)
class SyntheticGraspingArm(Arm[SyntheticPincer]):
    """
    The gantry arm of :class:`SyntheticGraspingRobot`, which slides its pincer along all
    three axes.
    """

    def setup_hardware_interfaces(self):
        self._setup_hardware_interfaces_for_active_connections()

    def setup_joint_states(self) -> List[JointState]:
        arm_park = JointState.from_mapping(
            name=PrefixedName("arm_park", prefix=self.name.name),
            mapping={
                self._world.get_connection_by_name(name): 0.0
                for name in ("bridge_joint", "carriage_joint", "lift_joint")
            },
            state_type=StaticJointState.PARK,
        )
        return [arm_park]

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        world = robot_root._world
        return cls(
            root=world.get_body_in_branch_by_name(robot_root, "base_link"),
            tip=world.get_body_in_branch_by_name(robot_root, "pincer_link"),
        )


@dataclass(eq=False)
class SyntheticGraspingRobot(AbstractRobot, HasOneArm[SyntheticGraspingArm]):
    """
    A fixed-base gantry robot with a two-fingered pincer, standing in for "some robot
    that can pick a Montessori piece up".
    """

    @classmethod
    def get_ros_file_path(cls) -> str:
        return SYNTHETIC_GRASPING_ROBOT_URDF_PATH

    @classmethod
    def _get_root_body_name(cls) -> str:
        return "base_link"

    def _setup_collision_rules(self):
        pass

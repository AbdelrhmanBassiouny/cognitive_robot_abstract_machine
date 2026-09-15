from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Self, List

from typing_extensions import Dict, Tuple

from semantic_digital_twin.collision_checking.collision_rules import (
    AvoidExternalCollisions,
    AvoidSelfCollisions,
    SelfCollisionMatrixRule,
)
from semantic_digital_twin.datastructures.definitions import (
    GripperState,
    StaticJointState,
)
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.robot_part_mixins import (
    HasLeftRightArm,
    HasTwoFingers,
    TGenericLeftFinger,
    TGenericRightFinger,
    HasEndEffector,
    HasSensors,
)
from semantic_digital_twin.robots.robot_parts import (
    AbstractRobot,
    Arm,
    Camera,
    Finger,
    EndEffector,
)
from semantic_digital_twin.datastructures.field_of_view import FieldOfView
from semantic_digital_twin.spatial_types import Quaternion, Vector3
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connection_properties import (
    JointDynamics,
    ServoGains,
)
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
)


class TracyJoint(StrEnum):
    """
    Names of the Tracy's commandable connections, as spelled in its URDF.

    Members are usable wherever a connection name is expected, so a configuration keyed by
    them stays a plain mapping of names to positions.

    ..note:: Connections that no controller commands, such as the grippers' inner knuckle
        and finger tip joints, are left out.
    """

    LEFT_SHOULDER_PAN = "left_shoulder_pan_joint"
    LEFT_SHOULDER_LIFT = "left_shoulder_lift_joint"
    LEFT_ELBOW = "left_elbow_joint"
    LEFT_WRIST_1 = "left_wrist_1_joint"
    LEFT_WRIST_2 = "left_wrist_2_joint"
    LEFT_WRIST_3 = "left_wrist_3_joint"
    LEFT_GRIPPER_LEFT_KNUCKLE = "left_robotiq_85_left_knuckle_joint"
    LEFT_GRIPPER_RIGHT_KNUCKLE = "left_robotiq_85_right_knuckle_joint"

    RIGHT_SHOULDER_PAN = "right_shoulder_pan_joint"
    RIGHT_SHOULDER_LIFT = "right_shoulder_lift_joint"
    RIGHT_ELBOW = "right_elbow_joint"
    RIGHT_WRIST_1 = "right_wrist_1_joint"
    RIGHT_WRIST_2 = "right_wrist_2_joint"
    RIGHT_WRIST_3 = "right_wrist_3_joint"
    RIGHT_GRIPPER_LEFT_KNUCKLE = "right_robotiq_85_left_knuckle_joint"
    RIGHT_GRIPPER_RIGHT_KNUCKLE = "right_robotiq_85_right_knuckle_joint"


@dataclass(eq=False)
class TracyLeftGripperLeftFinger(Finger):

    def setup_hardware_interfaces(self):
        pass

    def setup_joint_states(self) -> List[JointState]:
        return []

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        return cls(
            root=robot_root._world.get_body_in_branch_by_name(
                robot_root, "left_robotiq_85_left_knuckle_link"
            ),
            tip=robot_root._world.get_body_in_branch_by_name(
                robot_root, "left_robotiq_85_left_finger_tip_link"
            ),
        )


@dataclass(eq=False)
class TracyLeftGripperRightFinger(Finger):

    def setup_hardware_interfaces(self):
        pass

    def setup_joint_states(self) -> List[JointState]:
        return []

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        return cls(
            root=robot_root._world.get_body_in_branch_by_name(
                robot_root, "left_robotiq_85_right_knuckle_link"
            ),
            tip=robot_root._world.get_body_in_branch_by_name(
                robot_root, "left_robotiq_85_right_finger_tip_link"
            ),
        )


@dataclass(eq=False)
class TracyRightGripperLeftFinger(Finger):

    def setup_hardware_interfaces(self):
        pass

    def setup_joint_states(self) -> List[JointState]:
        return []

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        return cls(
            root=robot_root._world.get_body_in_branch_by_name(
                robot_root, "right_robotiq_85_left_knuckle_link"
            ),
            tip=robot_root._world.get_body_in_branch_by_name(
                robot_root, "right_robotiq_85_left_finger_tip_link"
            ),
        )


@dataclass(eq=False)
class TracyRightGripperRightFinger(Finger):

    def setup_hardware_interfaces(self):
        pass

    def setup_joint_states(self) -> List[JointState]:
        return []

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        return cls(
            root=robot_root._world.get_body_in_branch_by_name(
                robot_root, "right_robotiq_85_right_knuckle_link"
            ),
            tip=robot_root._world.get_body_in_branch_by_name(
                robot_root, "right_robotiq_85_right_finger_tip_link"
            ),
        )


class Robotiq85GripperGeometry(ABC):
    """
    What a grasp and a physical simulation have to know about one of Tracy's Robotiq
    2F-85 grippers: the pads that meet an object, the joint that drives the fingers,
    how far that joint has to turn to close the pads to a given width, and the servo
    driving it.

    Listed before the robot-part bases of a gripper, so that its answers take
    precedence over the parts' own defaults.
    """

    @property
    @abstractmethod
    def knuckle_joint(self) -> TracyJoint:
        """
        The joint that actually drives the gripper; every other finger joint in the
        mimic linkage follows it.
        """

    @property
    def finger_velocity_limit(self) -> float:
        """
        Velocity limit, in radians per second, every finger joint gets instead of the
        description's own: that one is roughly ``0.032`` rad/s, takes about 25 seconds
        to close the gripper, and no hardware reference backs it.

        ``1.0`` converges cleanly under joint-space planning, while ``2.0`` was measured
        to leave the QP solver settled short of its target.
        """
        return 1.0

    def servo_for(
        self, connection: ActiveConnection1DOF
    ) -> Tuple[ServoGains, JointDynamics]:
        """
        Every finger joint's servo, raised empirically since no pre-tuned reference
        exists for the Robotiq 2F-85, and the armature that gives the coupled mechanism
        the numerical damping keeping it from chattering under load.

        :param connection: One of the gripper's finger joints.
        :return: The servo's gains and the joint's dynamics.
        """
        return (
            ServoGains(stiffness=100.0, damping=10.0, torque_limit=10.0),
            JointDynamics(armature=0.05),
        )

    def prepare_for_physical_simulation(self) -> None:
        """
        Give every finger joint's degree of freedom :attr:`finger_velocity_limit`,
        overriding the description's own conservative one: kinematic planning has no
        reason to trust it, but a physically simulated servo needs the room to actually
        reach a commanded position within a plan's own convergence tolerance.
        """
        for connection in self.active_connections:
            if not isinstance(connection, ActiveConnection1DOF):
                continue
            connection.raw_dof.limits.upper.velocity = self.finger_velocity_limit
            connection.raw_dof.limits.lower.velocity = -self.finger_velocity_limit

    @property
    def left_fingertip(self) -> Body:
        """
        The left fingertip pad's body.
        """
        return self.thumb.tip

    @property
    def right_fingertip(self) -> Body:
        """
        The right fingertip pad's body.
        """
        return self.finger.tip

    @property
    def knuckle_degree_of_freedom(self) -> DegreeOfFreedom:
        """
        The raw degree of freedom driving the knuckle.
        """
        return self._world.get_connection_by_name(self.knuckle_joint).raw_dof

    def knuckle_angle_for_half_width(
        self, target_half_width: float, iterations: int = 30
    ) -> float:
        """
        The knuckle's raw angle at which the fingertip pads' inner faces first reach
        ``target_half_width`` out from the gripper's own centreline: what to command the
        knuckle to for closing the fingers on an object of twice that width.

        Closing all the way on an object that is not perfectly centred between the
        fingers wedges it sideways rather than gripping it, so a grasp closes to the
        object's width instead. The pad's inner position decreases monotonically as the
        knuckle closes, so bisection against an isolated scratch copy of the world
        converges reliably; the world itself is never modified.

        :param target_half_width: The half-width, in metres, to close to.
        :param iterations: Bisection steps; 30 narrows the joint's own ~0.8 rad range to
            well under a micro-radian.
        :return: The raw angle.
        """
        scratch_world = deepcopy(self._world)
        [scratch_gripper] = scratch_world.get_semantic_annotations_by_type(type(self))
        raw_dof = scratch_gripper.knuckle_degree_of_freedom
        left_fingertip = scratch_gripper.left_fingertip

        def inner_x(raw_angle: float) -> float:
            """
            The left pad's innermost point along the closing axis at one raw angle,
            moving the scratch world's own state directly.
            """
            scratch_world.state[raw_dof.id].position = raw_angle
            scratch_world.notify_state_change()
            scratch_world.update_forward_kinematics()
            return (
                left_fingertip.collision.as_bounding_box_collection_in_frame(
                    scratch_gripper.root
                )
                .bounding_box()
                .min_x
            )

        lower, upper = raw_dof.limits.lower.position, raw_dof.limits.upper.position
        if target_half_width >= inner_x(lower):
            return lower
        if target_half_width <= inner_x(upper):
            return upper
        for _ in range(iterations):
            midpoint = (lower + upper) / 2
            if inner_x(midpoint) > target_half_width:
                lower = midpoint
            else:
                upper = midpoint
        return upper


@dataclass(eq=False)
class TracyLeftGripper(
    Robotiq85GripperGeometry,
    EndEffector,
    HasTwoFingers[TracyLeftGripperLeftFinger, TracyLeftGripperRightFinger],
):

    @property
    def knuckle_joint(self) -> TracyJoint:
        return TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE

    def setup_hardware_interfaces(self):
        self._setup_hardware_interfaces_for_active_connections()

    def setup_joint_states(self) -> List[JointState]:
        left_gripper_joints = [
            self._world.get_connection_by_name(TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE),
            self._world.get_connection_by_name(TracyJoint.LEFT_GRIPPER_RIGHT_KNUCKLE),
        ]

        gripper_open = JointState.from_mapping(
            name=PrefixedName("left_gripper_open", prefix=self.name.name),
            mapping=dict(zip(left_gripper_joints, [0.0, 0.0])),
            state_type=GripperState.OPEN,
        )

        gripper_close = JointState.from_mapping(
            name=PrefixedName("left_gripper_close", prefix=self.name.name),
            mapping=dict(
                zip(
                    left_gripper_joints,
                    [
                        0.8,
                        -0.8,
                    ],
                )
            ),
            state_type=GripperState.CLOSE,
        )
        return [gripper_open, gripper_close]

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        return cls(
            root=robot_root._world.get_body_in_branch_by_name(
                robot_root, "left_robotiq_85_base_link"
            ),
            tool_frame=robot_root._world.get_body_in_branch_by_name(
                robot_root, "l_gripper_tool_frame"
            ),
            front_facing_orientation=Quaternion(0.5, 0.5, 0.5, 0.5),
        )


@dataclass(eq=False)
class TracyRightGripper(
    Robotiq85GripperGeometry,
    EndEffector,
    HasTwoFingers[TracyRightGripperLeftFinger, TracyRightGripperRightFinger],
):

    @property
    def knuckle_joint(self) -> TracyJoint:
        return TracyJoint.RIGHT_GRIPPER_LEFT_KNUCKLE

    def setup_hardware_interfaces(self):
        self._setup_hardware_interfaces_for_active_connections()

    def setup_joint_states(self) -> List[JointState]:
        right_gripper_joints = [
            self._world.get_connection_by_name(TracyJoint.RIGHT_GRIPPER_LEFT_KNUCKLE),
            self._world.get_connection_by_name(TracyJoint.RIGHT_GRIPPER_RIGHT_KNUCKLE),
        ]

        gripper_open = JointState.from_mapping(
            name=PrefixedName("right_gripper_open", prefix=self.name.name),
            mapping=dict(zip(right_gripper_joints, [0.0, 0.0])),
            state_type=GripperState.OPEN,
        )

        gripper_close = JointState.from_mapping(
            name=PrefixedName("right_gripper_close", prefix=self.name.name),
            mapping=dict(zip(right_gripper_joints, [0.8, -0.8])),
            state_type=GripperState.CLOSE,
        )

        return [gripper_open, gripper_close]

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        return cls(
            root=robot_root._world.get_body_in_branch_by_name(
                robot_root, "right_robotiq_85_base_link"
            ),
            tool_frame=robot_root._world.get_body_in_branch_by_name(
                robot_root, "r_gripper_tool_frame"
            ),
            front_facing_orientation=Quaternion(0.5, 0.5, 0.5, 0.5),
        )


class UR10eServos:
    """
    The position servos of a UR10e arm's joints when it is simulated physically, taken
    from MuJoCo Menagerie's ``universal_robots_ur10e/ur10e.xml``: a stiffness of 5000, a
    servo damping of 500 and an armature of 0.1 apply to every joint regardless of size,
    and only the torque limit and the joint's passive damping differ per size class.

    Tracy's own UR10 arms are close enough to reuse this.
    """

    @staticmethod
    def _size_class(
        torque_limit: float, joint_damping: float
    ) -> Tuple[ServoGains, JointDynamics]:
        return (
            ServoGains(stiffness=5_000.0, damping=500.0, torque_limit=torque_limit),
            JointDynamics(armature=0.1, damping=joint_damping),
        )

    @property
    def servos_by_joint(self) -> Dict[str, Tuple[ServoGains, JointDynamics]]:
        """
        Each joint's servo gains and joint dynamics, keyed by the joint's name without
        the arm's ``left_``/``right_`` prefix.

        The two shoulder joints carry the whole rest of the arm and need the most torque
        and passive damping to settle without ringing, the elbow less, and the three
        wrist joints, which carry only the gripper, the least.
        """
        shoulder = self._size_class(torque_limit=330.0, joint_damping=10.0)
        elbow = self._size_class(torque_limit=150.0, joint_damping=5.0)
        wrist = self._size_class(torque_limit=56.0, joint_damping=2.0)
        return {
            "shoulder_pan_joint": shoulder,
            "shoulder_lift_joint": shoulder,
            "elbow_joint": elbow,
            "wrist_1_joint": wrist,
            "wrist_2_joint": wrist,
            "wrist_3_joint": wrist,
        }

    def servo_for(
        self, connection: ActiveConnection1DOF
    ) -> Tuple[ServoGains, JointDynamics]:
        """
        :param connection: One of the arm's joints.
        :return: Its servo gains and joint dynamics, by the joint's name without the
            arm's ``left_``/``right_`` prefix.
        """
        joint_name = connection.raw_dof.name.name
        unprefixed = joint_name.removeprefix("left_").removeprefix("right_")
        return self.servos_by_joint[unprefixed]


@dataclass(eq=False)
class TracyLeftArm(UR10eServos, Arm[TracyLeftGripper]):

    def setup_hardware_interfaces(self):
        self._setup_hardware_interfaces_for_active_connections()

    def setup_joint_states(self) -> List[JointState]:
        connections = self.active_connections
        arm_park = JointState.from_mapping(
            name=PrefixedName("left_arm_park", prefix=self.name.name),
            mapping=dict(zip(connections, [2.62, -1.035, 1.13, -0.966, -0.88, 2.07])),
            state_type=StaticJointState.PARK,
        )
        return [arm_park]

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        return cls(
            root=robot_root._world.get_body_in_branch_by_name(robot_root, "table"),
            tip=robot_root._world.get_body_in_branch_by_name(
                robot_root, "left_wrist_3_link"
            ),
        )


@dataclass(eq=False)
class TracyRightArm(UR10eServos, Arm[TracyRightGripper]):

    def setup_hardware_interfaces(self):
        self._setup_hardware_interfaces_for_active_connections()

    def setup_joint_states(self) -> List[JointState]:
        connections = self.active_connections
        arm_park = JointState.from_mapping(
            name=PrefixedName("right_arm_park", prefix=self.name.name),
            mapping=dict(zip(connections, [3.72, -2.07, -1.17, 4.0, 0.82, 0.75])),
            state_type=StaticJointState.PARK,
        )
        return [arm_park]

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        return cls(
            root=robot_root._world.get_body_in_branch_by_name(robot_root, "table"),
            tip=robot_root._world.get_body_in_branch_by_name(
                robot_root, "right_wrist_3_link"
            ),
        )


@dataclass(eq=False)
class TracyCamera(Camera):

    def setup_hardware_interfaces(self):
        pass

    def setup_joint_states(self) -> List[JointState]:
        return []

    @classmethod
    def setup_default_configuration_in_world_below_robot_root(
        cls, robot_root: KinematicStructureEntity
    ) -> Self:
        return cls(
            root=robot_root._world.get_body_in_branch_by_name(
                robot_root, "camera_link"
            ),
            forward_facing_axis=Vector3.Z(),
            field_of_view=FieldOfView(horizontal_angle=1.047, vertical_angle=0.785),
            minimal_height=0.8,
            maximal_height=1.7,
            default_camera=True,
        )


@dataclass(eq=False)
class Tracy(
    AbstractRobot, HasLeftRightArm[TracyLeftArm, TracyRightArm], HasSensors[TracyCamera]
):
    """
    The dual UR10 arm setup used in the TraceBot project.

    https://vib.ai.uni-bremen.de/page/comingsoon/the-tracebot-laboratory/
    """

    @classmethod
    def get_ros_file_path(cls) -> str:
        return "package://iai_tracy_description/urdf/tracy.urdf.xacro"

    @classmethod
    def _get_root_body_name(cls) -> str:
        return "table"

    def _setup_collision_rules(self):
        srdf_path = os.path.join(
            Path(files("semantic_digital_twin")).parent.parent,
            "resources",
            "collision_configs",
            "tracy.srdf",
        )
        self._world.collision_manager.add_ignore_collision_rule(
            SelfCollisionMatrixRule.from_collision_srdf(srdf_path, self._world)
        )

        self._world.collision_manager.extend_default_rules(
            [
                AvoidExternalCollisions(
                    buffer_zone_distance=0.05, violated_distance=0.0, robot=self
                ),
                AvoidSelfCollisions(
                    buffer_zone_distance=0.03,
                    violated_distance=0.0,
                    robot=self,
                ),
            ]
        )

    def _setup_velocity_limits(self):
        self.tighten_dof_velocity_limits_proportionally(maximum_velocity=0.2)

    def get_end_effectors(self) -> list[EndEffector]:
        return [self.left_arm.end_effector, self.right_arm.end_effector]

    @staticmethod
    def floor_mount_pose(tracy_world: World, x: float, y: float) -> Pose:
        """
        Where to bolt a parsed, not yet mounted Tracy so that its own table's legs rest
        exactly on the floor.

        :param tracy_world: Tracy's own parsed world, as :meth:`parse_description`
            returns it, not yet merged into anything.
        :param x: Where to mount Tracy's root along the merge target's x-axis.
        :param y: Where to mount Tracy's root along the merge target's y-axis.
        :return: The mount pose, in the merge target's root frame.
        """
        table = tracy_world.get_body_by_name("table")
        table_bounding_box = table.collision.as_bounding_box_collection_in_frame(
            tracy_world.root
        ).bounding_box()
        return Pose.from_xyz_rpy(x=x, y=y, z=-table_bounding_box.min_z)

    @property
    def table_top_z(self) -> float:
        """
        Height of this mounted Tracy's own table top above the world root, in metres.
        """
        table = self.root
        tabletop = max(table.collision, key=lambda shape: shape.scale.x * shape.scale.y)
        root_transform_table = self._world.compute_forward_kinematics_np(
            self._world.root, table
        )
        return float(
            root_transform_table[2, 3]
            + tabletop.origin.to_np()[2, 3]
            + tabletop.scale.z / 2
        )

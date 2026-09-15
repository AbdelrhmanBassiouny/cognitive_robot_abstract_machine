from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Self, List

from typing_extensions import Dict, Tuple

from semantic_digital_twin.adapters.mujoco_tuning import (
    ServoGains,
    compensate_gravity,
    equip_with_servos,
    exclude_self_collision,
)
from semantic_digital_twin.adapters.urdf import URDFParser
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
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.world_entity import (
    Actuator,
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
    What a grasp has to know about one of Tracy's Robotiq 2F-85 grippers: the pads that
    meet an object, the joint that drives the fingers, and how far that joint has to
    turn to close the pads to a given width.
    """

    @property
    @abstractmethod
    def knuckle_joint(self) -> TracyJoint:
        """
        The joint that actually drives the gripper; every other finger joint in the
        mimic linkage follows it.
        """

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
        ``target_half_width`` out from the gripper's own centreline.

        The pad's inner position decreases monotonically as the knuckle closes, so
        bisection against an isolated scratch copy of the world converges reliably; the
        world itself is never modified.

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
    EndEffector,
    HasTwoFingers[TracyLeftGripperLeftFinger, TracyLeftGripperRightFinger],
    Robotiq85GripperGeometry,
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
    EndEffector,
    HasTwoFingers[TracyRightGripperLeftFinger, TracyRightGripperRightFinger],
    Robotiq85GripperGeometry,
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


@dataclass(eq=False)
class TracyLeftArm(Arm[TracyLeftGripper]):

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
class TracyRightArm(Arm[TracyRightGripper]):

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


@dataclass(frozen=True)
class TracyServoTuning:
    """
    The position servos Tracy's arms and grippers are equipped with when it is simulated
    physically in MuJoCo.
    """

    arm_joint_gains: Dict[str, ServoGains] = field(
        default_factory=lambda: TracyServoTuning.ur10e_arm_gains()
    )
    """
    Each arm joint's gains, keyed by joint name without the arm's ``left_``/``right_``
    prefix.
    """

    gripper_joint_gains: ServoGains = field(
        default_factory=lambda: TracyServoTuning.robotiq_85_knuckle_gains()
    )
    """
    The gains of every gripper joint.
    """

    gripper_joint_velocity_limit: float = 1.0
    """
    Velocity limit, in radians per second, given to every gripper joint's degree of
    freedom, overriding the description's own.

    The description's knuckle joint velocity limit is roughly ``0.032`` rad/s, at which
    closing through the gripper's ~0.8 rad range takes about 25 seconds, and no hardware
    reference backs that number. ``1.0`` converges cleanly under joint-space planning;
    ``2.0`` was measured to leave the QP solver settled about 0.016 rad short of its
    target indefinitely.
    """

    @staticmethod
    def ur10e_gains(torque_limit: float, joint_damping: float) -> ServoGains:
        """
        The gains of one UR10e joint size class, taken from MuJoCo Menagerie's
        ``universal_robots_ur10e/ur10e.xml``: its stiffness of 5000, actuator damping of
        500 and armature of 0.1 apply to every joint regardless of size, and only the
        torque limit and the joint's passive damping differ per size class. Tracy's own
        UR10 arms are close enough to reuse this.

        :param torque_limit: The size class's torque limit, in newton metres.
        :param joint_damping: The size class's passive joint damping.
        :return: The gains.
        """
        return ServoGains(
            stiffness=5_000.0,
            actuator_damping=500.0,
            torque_limit=torque_limit,
            joint_damping=joint_damping,
            armature=0.1,
        )

    @classmethod
    def ur10e_arm_gains(cls) -> Dict[str, ServoGains]:
        """
        The per-joint gains of a UR10e arm, keyed by joint name without a ``left_``/
        ``right_`` prefix.

        The two shoulder joints carry the whole rest of the arm and need the most torque
        and passive damping to settle without ringing, the elbow less, and the three
        wrist joints, which carry only the gripper, the least.

        :return: The gains of every arm joint.
        """
        return {
            "shoulder_pan_joint": cls.ur10e_gains(
                torque_limit=330.0, joint_damping=10.0
            ),
            "shoulder_lift_joint": cls.ur10e_gains(
                torque_limit=330.0, joint_damping=10.0
            ),
            "elbow_joint": cls.ur10e_gains(torque_limit=150.0, joint_damping=5.0),
            "wrist_1_joint": cls.ur10e_gains(torque_limit=56.0, joint_damping=2.0),
            "wrist_2_joint": cls.ur10e_gains(torque_limit=56.0, joint_damping=2.0),
            "wrist_3_joint": cls.ur10e_gains(torque_limit=56.0, joint_damping=2.0),
        }

    @staticmethod
    def robotiq_85_knuckle_gains() -> ServoGains:
        """
        The gains of a Robotiq 2F-85 knuckle joint, raised empirically; no pre-tuned
        reference exists for this gripper.

        :return: The gains.
        """
        return ServoGains(
            stiffness=100.0,
            actuator_damping=10.0,
            torque_limit=10.0,
            joint_damping=0.0,
            armature=0.05,
        )

    def arm_gains_for(self, joint_name: str) -> ServoGains:
        """
        :param joint_name: Name of an arm joint, possibly ``left_``/``right_``-prefixed.
        :return: Its gains.
        """
        unprefixed = joint_name.removeprefix("left_").removeprefix("right_")
        return self.arm_joint_gains[unprefixed]


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

    @classmethod
    def parse_description(
        cls, mount_root_name: PrefixedName = PrefixedName("tracy_mount", "tracy")
    ) -> World:
        """
        Read Tracy out of its own ROS package into a world of its own, without any
        actuator, ready to be mounted into another world with :meth:`mount_stationary`.

        :param mount_root_name: Name given to the parsed world's synthetic root, so it
            never collides with a merge target's own root. Tracy's real kinematic root,
            its table, is a descendant of that node, so renaming it does not affect
            :meth:`from_world`'s later lookup.
        :return: A world holding only Tracy's own body tree.
        """
        tracy_world = URDFParser.from_file(cls.get_ros_file_path()).parse()
        with tracy_world.modify_world():
            for actuator in list(tracy_world.actuators):
                tracy_world.remove_actuator(actuator)
            tracy_world.root.name = mount_root_name
        return tracy_world

    @staticmethod
    def floor_mount_position(
        tracy_world: World, x: float, y: float
    ) -> Tuple[Point3, float]:
        """
        Where to bolt a parsed, not yet mounted Tracy so that its own table's legs rest
        exactly on the floor, and the height its table top ends up at.

        :param tracy_world: Tracy's own parsed world, as :meth:`parse_description`
            returns it, not yet merged into anything.
        :param x: Where to mount Tracy's root along the merge target's x-axis.
        :param y: Where to mount Tracy's root along the merge target's y-axis.
        :return: The mount position, and the height of the table top above the floor
            once mounted there, both in metres.
        """
        table = tracy_world.get_body_by_name("table")
        table_bounding_box = table.collision.as_bounding_box_collection_in_frame(
            tracy_world.root
        ).bounding_box()
        mount_z = -table_bounding_box.min_z
        tabletop = max(table.collision, key=lambda shape: shape.scale.x * shape.scale.y)
        root_transform_table = tracy_world.compute_forward_kinematics_np(
            tracy_world.root, table
        )
        tabletop_top_z = float(tabletop.origin.to_np()[2, 3] + tabletop.scale.z / 2)
        table_top_z = mount_z + float(root_transform_table[2, 3]) + tabletop_top_z
        return Point3(x, y, mount_z), table_top_z

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

    def equip_for_mujoco(
        self, tuning: TracyServoTuning = TracyServoTuning()
    ) -> Dict[str, Actuator]:
        """
        Prepare this mounted Tracy to be simulated physically: a position servo on every
        arm and gripper joint, gravity compensation on every link, and no collision
        between its own links.

        :param tuning: The servos to equip.
        :return: Each driven degree of freedom's actuator, keyed by joint name.
        """
        world = self._world
        compensate_gravity(world, self)
        exclude_self_collision(world, self)
        return {
            **self.equip_arms_with_servos(tuning),
            **self.equip_grippers_with_servos(tuning),
        }

    def equip_arms_with_servos(
        self, tuning: TracyServoTuning = TracyServoTuning()
    ) -> Dict[str, Actuator]:
        """
        Give every joint of both arms a position servo, its own passive damping and
        armature.

        :param tuning: The servos to equip.
        :return: Each driven degree of freedom's actuator, keyed by joint name.
        """
        connections = [
            connection
            for arm in self.get_arms()
            for connection in arm.active_connections
            if isinstance(connection, ActiveConnection1DOF)
        ]
        return equip_with_servos(
            self._world,
            connections,
            {
                connection.raw_dof.name.name: tuning.arm_gains_for(
                    connection.raw_dof.name.name
                )
                for connection in connections
            },
        )

    def equip_grippers_with_servos(
        self, tuning: TracyServoTuning = TracyServoTuning()
    ) -> Dict[str, Actuator]:
        """
        Give every joint of both grippers a position servo, and raise every gripper
        joint's velocity limit to the tuning's.

        :param tuning: The servos to equip.
        :return: Each driven degree of freedom's actuator, keyed by joint name.
        """
        connections = [
            connection
            for arm in self.get_arms()
            for connection in arm.end_effector.active_connections
            if isinstance(connection, ActiveConnection1DOF)
        ]
        with self._world.modify_world():
            for degree_of_freedom in {connection.raw_dof for connection in connections}:
                degree_of_freedom.limits.upper.velocity = (
                    tuning.gripper_joint_velocity_limit
                )
                degree_of_freedom.limits.lower.velocity = (
                    -tuning.gripper_joint_velocity_limit
                )
        return equip_with_servos(
            self._world,
            connections,
            {
                connection.raw_dof.name.name: tuning.gripper_joint_gains
                for connection in connections
            },
        )

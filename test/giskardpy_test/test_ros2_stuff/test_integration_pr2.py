from __future__ import division

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from time import sleep
from typing import Set

import numpy as np
import pytest
from numpy import pi

import semantic_digital_twin.spatial_types.spatial_types as cas
from giskardpy.middleware.ros2.server_config import ExecutionMode, GiskardServerConfig
from giskardpy.middleware.ros2.scripts.iai_robots.pr2.configs import (
    PR2StandaloneInterface,
    WorldWithPR2Config,
)
from giskardpy.middleware.ros2.giskard import Giskard
from giskardpy.middleware.ros2.rospy import wait_for_future_to_complete
from giskardpy.middleware.ros2.utils.utils import load_xacro
from giskardpy.middleware.ros2.utils.utils_for_tests import (
    GiskardTester,
    compare_points,
)
from giskardpy.motion_statechart.data_types import DefaultWeights
from cramph.data_types import ObservationStateValues
from cramph.exceptions import EmptyStatechartError
from giskardpy.motion_statechart.exceptions import CollisionViolatedError
from giskardpy.motion_statechart.goals.collision_avoidance import (
    ExternalCollisionAvoidance,
    SelfCollisionAvoidance,
    UpdateTemporaryCollisionRules,
)
from cramph.composites import Parallel, Sequence
from giskardpy.motion_statechart.goals.tracebot import InsertCylinder
from giskardpy.motion_statechart.graph_node import EndMotion
from cramph.node import CancelStatechart
from giskardpy.motion_statechart.monitors.monitors import LocalMinimumReached
from giskardpy.motion_statechart.monitors.overwrite_state_monitors import (
    SetOdometry,
    SetSeedConfiguration,
)
from cramph.monitors import CountSeconds, CountSimulationTimeSeconds
from cramph.statechart import Statechart
from giskardpy.motion_statechart.tasks.align_planes import AlignPlanes
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianPose,
)
from giskardpy.motion_statechart.tasks.joint_tasks import (
    JointPositionList,
    JointState,
)
from giskardpy.motion_statechart.tasks.pointing import Pointing
from giskardpy.qp.qp_controller_config import QPControllerConfig
from giskardpy.middleware.ros2.exceptions import (
    ClientDisconnectedError,
    ExecutionCanceledException,
    ExecutionAbortedException,
    WorldModelModifiedDuringMotionError,
)
from krrood.symbolic_math import symbolic_math as sm
from semantic_digital_twin.collision_checking.collision_rules import (
    AvoidExternalCollisions,
    AvoidCollisionBetweenGroups,
)
from semantic_digital_twin.robots.pr2 import PR2Joint
from semantic_digital_twin.robots.robot_parts import EndEffector, AbstractRobot
from semantic_digital_twin.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
    RotationMatrix,
    Vector3,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.connections import (
    RevoluteConnection,
    ActiveConnection1DOF,
)
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
)

from .test_client_presence import wait_until


@dataclass
class PR2Tester(GiskardTester):

    better_pose_right = {
        PR2Joint.RIGHT_SHOULDER_PAN: -1.7125,
        PR2Joint.RIGHT_SHOULDER_LIFT: -0.25672,
        PR2Joint.RIGHT_UPPER_ARM_ROLL: -1.46335,
        PR2Joint.RIGHT_ELBOW_FLEX: -2.12,
        PR2Joint.RIGHT_FOREARM_ROLL: 1.76632,
        PR2Joint.RIGHT_WRIST_FLEX: -0.10001,
        PR2Joint.RIGHT_WRIST_ROLL: 0.05106,
    }

    better_pose_left = {
        PR2Joint.LEFT_SHOULDER_PAN: 1.9652,
        PR2Joint.LEFT_SHOULDER_LIFT: -0.26499,
        PR2Joint.LEFT_UPPER_ARM_ROLL: 1.3837,
        PR2Joint.LEFT_ELBOW_FLEX: -2.12,
        PR2Joint.LEFT_FOREARM_ROLL: 16.99,
        PR2Joint.LEFT_WRIST_FLEX: -0.10001,
        PR2Joint.LEFT_WRIST_ROLL: 0,
    }

    right_tip: KinematicStructureEntity = field(init=False)
    left_tip: KinematicStructureEntity = field(init=False)
    odom_combined: KinematicStructureEntity = field(init=False)

    def __post_init__(self):
        super().__post_init__()
        self.left_tip = self.api.world.get_kinematic_structure_entity_by_name(
            "l_gripper_tool_frame"
        )
        self.right_tip = self.api.world.get_kinematic_structure_entity_by_name(
            "r_gripper_tool_frame"
        )
        self.camera = self.api.world.get_kinematic_structure_entity_by_name(
            "head_mount_kinect_rgb_link"
        )
        self.odom_combined = self.api.world.get_kinematic_structure_entity_by_name(
            "odom_combined"
        )
        self.base_footprint = self.api.world.get_kinematic_structure_entity_by_name(
            "base_footprint"
        )
        self.base_link = self.api.world.get_kinematic_structure_entity_by_name(
            "base_link"
        )
        self.torso_lift_link = self.api.world.get_kinematic_structure_entity_by_name(
            "torso_lift_link"
        )
        self.map = self.api.world.get_kinematic_structure_entity_by_name("map")

    def setup_giskard(self) -> Giskard:
        robot_desc = load_xacro(
            "package://iai_pr2_description/robots/pr2_with_ft2_cableguide.xacro"
        )
        return Giskard(
            world_config=WorldWithPR2Config(urdf=robot_desc),
            robot_interface_config=PR2StandaloneInterface(),
            server_config=GiskardServerConfig(
                execution_mode=ExecutionMode.STANDALONE,
                debug_mode=True,
                plot_trajectory=True,
            ),
            qp_controller_config=QPControllerConfig(
                target_frequency=20,
            ),
        )

    @property
    def robot(self) -> AbstractRobot:
        return self.giskard.executor.context.world.get_semantic_annotation_by_name(
            self.api.robot_name
        )

    @property
    def l_gripper_annotation(self) -> EndEffector:
        return next(
            end_effector
            for end_effector in self.robot.all_end_effectors
            if "left" in str(end_effector.name).lower()
        )

    @property
    def r_gripper_annotation(self) -> EndEffector:
        return next(
            end_effector
            for end_effector in self.robot.all_end_effectors
            if "right" in str(end_effector.name).lower()
        )

    def get_l_gripper_links(self) -> Set[Body]:
        return set(b for b in self.l_gripper_annotation.bodies if b.has_collision())

    def get_r_gripper_links(self) -> Set[Body]:
        return set(b for b in self.r_gripper_annotation.bodies if b.has_collision())

    def get_r_forearm_links(self):
        return [
            "r_wrist_flex_link",
            "r_wrist_roll_link",
            "r_forearm_roll_link",
            "r_forearm_link",
            "r_forearm_link",
        ]

    def open_r_gripper(self):
        return

    def close_r_gripper(self):
        return

    def open_l_gripper(self):
        return

    def close_l_gripper(self):
        return


@pytest.fixture()
def robot():
    c = PR2Tester()
    try:
        yield c
    finally:
        print("tear down")
        c.close()


@pytest.fixture()
def default_joint_state():
    return {
        PR2Joint.RIGHT_ELBOW_FLEX: -0.15,
        PR2Joint.RIGHT_FOREARM_ROLL: 0,
        PR2Joint.RIGHT_SHOULDER_LIFT: 0,
        PR2Joint.RIGHT_SHOULDER_PAN: 0,
        PR2Joint.RIGHT_UPPER_ARM_ROLL: 0,
        PR2Joint.RIGHT_WRIST_FLEX: -0.10001,
        PR2Joint.RIGHT_WRIST_ROLL: 0,
        PR2Joint.LEFT_ELBOW_FLEX: -0.15,
        PR2Joint.LEFT_FOREARM_ROLL: 0,
        PR2Joint.LEFT_SHOULDER_LIFT: 0,
        PR2Joint.LEFT_SHOULDER_PAN: 0,
        PR2Joint.LEFT_UPPER_ARM_ROLL: 0,
        PR2Joint.LEFT_WRIST_FLEX: -0.10001,
        PR2Joint.LEFT_WRIST_ROLL: 0,
        PR2Joint.TORSO_LIFT: 0.2,
        PR2Joint.HEAD_PAN: 0,
        PR2Joint.HEAD_TILT: 0,
        PR2Joint.LEFT_GRIPPER_LEFT_FINGER: 0.55,
        PR2Joint.RIGHT_GRIPPER_LEFT_FINGER: 0.55,
    }


@pytest.fixture()
def pocky_pose_state():
    return {
        PR2Joint.RIGHT_ELBOW_FLEX: -1.29610152504,
        PR2Joint.RIGHT_FOREARM_ROLL: -0.0301682323805,
        PR2Joint.RIGHT_SHOULDER_LIFT: 1.20324921318,
        PR2Joint.RIGHT_SHOULDER_PAN: -0.73456435706,
        PR2Joint.RIGHT_UPPER_ARM_ROLL: -0.70790051778,
        PR2Joint.RIGHT_WRIST_FLEX: -0.10001,
        PR2Joint.RIGHT_WRIST_ROLL: 0.258268529825,
        PR2Joint.LEFT_ELBOW_FLEX: -1.29610152504,
        PR2Joint.LEFT_FOREARM_ROLL: 0.0301682323805,
        PR2Joint.LEFT_SHOULDER_LIFT: 1.20324921318,
        PR2Joint.LEFT_SHOULDER_PAN: 0.73456435706,
        PR2Joint.LEFT_UPPER_ARM_ROLL: 0.70790051778,
        PR2Joint.LEFT_WRIST_FLEX: -0.1001,
        PR2Joint.LEFT_WRIST_ROLL: -0.258268529825,
        PR2Joint.TORSO_LIFT: 0.2,
        PR2Joint.HEAD_PAN: 0,
        PR2Joint.HEAD_TILT: 0,
        PR2Joint.LEFT_GRIPPER_LEFT_FINGER: 0.55,
        PR2Joint.RIGHT_GRIPPER_LEFT_FINGER: 0.55,
    }


@pytest.fixture()
def better_pose():
    return {
        PR2Joint.RIGHT_SHOULDER_PAN: -1.7125,
        PR2Joint.RIGHT_SHOULDER_LIFT: -0.25672,
        PR2Joint.RIGHT_UPPER_ARM_ROLL: -1.46335,
        PR2Joint.RIGHT_ELBOW_FLEX: -2.12,
        PR2Joint.RIGHT_FOREARM_ROLL: 1.76632,
        PR2Joint.RIGHT_WRIST_FLEX: -0.10001,
        PR2Joint.RIGHT_WRIST_ROLL: 0.05106,
        PR2Joint.LEFT_SHOULDER_PAN: 1.9652,
        PR2Joint.LEFT_SHOULDER_LIFT: -0.26499,
        PR2Joint.LEFT_UPPER_ARM_ROLL: 1.3837,
        PR2Joint.LEFT_ELBOW_FLEX: -2.12,
        PR2Joint.LEFT_FOREARM_ROLL: 16.99,
        PR2Joint.LEFT_WRIST_FLEX: -0.10001,
        PR2Joint.LEFT_WRIST_ROLL: 0,
        PR2Joint.TORSO_LIFT: 0.2,
        PR2Joint.LEFT_GRIPPER_LEFT_FINGER: 0.55,
        PR2Joint.RIGHT_GRIPPER_LEFT_FINGER: 0.55,
        PR2Joint.HEAD_PAN: 0,
        PR2Joint.HEAD_TILT: 0,
    }


@pytest.fixture()
def pocky_pose_setup(giskard_factory, pocky_pose_state):
    return giskard_factory(pocky_pose_state)


@pytest.fixture()
def box_setup(pocky_pose_setup: PR2Tester) -> PR2Tester:
    pocky_pose_setup.add_box_to_world(
        name="box",
        size=(1.0, 1.0, 1.0),
        pose=HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1.2, z=0.5, reference_frame=pocky_pose_setup.map
        ),
    )
    return pocky_pose_setup


@pytest.fixture()
def fake_table_setup(pocky_pose_setup: PR2Tester) -> PR2Tester:
    pocky_pose_setup.add_box_to_world(
        name="box",
        size=(1.0, 1.0, 1.0),
        pose=HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1.2, z=0.3, reference_frame=pocky_pose_setup.map
        ),
    )
    return pocky_pose_setup


class TestJointGoals:
    def test_joint_goal(self, giskard: PR2Tester):
        js = {
            PR2Joint.TORSO_LIFT: 0.2999225173357618,
            PR2Joint.HEAD_PAN: 0.041880780651479044,
            PR2Joint.HEAD_TILT: -0.37,
            PR2Joint.RIGHT_UPPER_ARM_ROLL: -0.9487714747527726,
            PR2Joint.RIGHT_SHOULDER_PAN: -1.0047307505973626,
            PR2Joint.RIGHT_SHOULDER_LIFT: 0.48736790658811985,
            PR2Joint.RIGHT_FOREARM_ROLL: -14.895833882874182,
            PR2Joint.RIGHT_ELBOW_FLEX: -1.392377908925028,
            PR2Joint.RIGHT_WRIST_FLEX: -0.4548695149411013,
            PR2Joint.RIGHT_WRIST_ROLL: 0.11426798984097819,
            PR2Joint.LEFT_UPPER_ARM_ROLL: 1.7383062350263658,
            PR2Joint.LEFT_SHOULDER_PAN: 1.8799810286792007,
            PR2Joint.LEFT_SHOULDER_LIFT: 0.011627231224188975,
            PR2Joint.LEFT_FOREARM_ROLL: 312.67276414458695,
            PR2Joint.LEFT_ELBOW_FLEX: -2.0300928925694675,
            PR2Joint.LEFT_WRIST_FLEX: -0.1,
            PR2Joint.LEFT_WRIST_ROLL: -6.062015047706399,
        }
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            joint_goal := JointPositionList(
                goal_state=JointState.from_str_dict(js, giskard.api.world),
            )
        )
        msc.add_node(EndMotion.when_true(joint_goal))
        giskard.api.compile(msc)
        giskard.api.execute()
        sleep(0.1)
        for joint, goal in js.items():
            connection = giskard.api.world.get_connection_by_name(joint)
            actual = giskard.api.world.state[connection.dof.id].position
            if (
                isinstance(connection, RevoluteConnection)
                and not connection.dof.has_position_limits()
            ):
                assert sm.shortest_angular_distance(actual, goal).to_np()[0] < 0.01
            else:
                try:
                    assert np.isclose(
                        actual,
                        goal,
                        atol=1e-2,
                    ), f"expected {actual} got {goal} for {connection.name}"
                except Exception as e:
                    pass

    def test_hard_joint_limits(self, giskard: PR2Tester):
        r_elbow_flex_joint: ActiveConnection1DOF = (
            giskard.api.world.get_connection_by_name(PR2Joint.RIGHT_ELBOW_FLEX)
        )
        torso_lift_joint: ActiveConnection1DOF = (
            giskard.api.world.get_connection_by_name(PR2Joint.TORSO_LIFT)
        )
        head_pan_joint: ActiveConnection1DOF = giskard.api.world.get_connection_by_name(
            PR2Joint.HEAD_PAN
        )
        msc = Statechart(context=giskard.api.context)

        min_joint_goal = JointPositionList(
            goal_state=JointState.from_mapping(
                mapping={
                    r_elbow_flex_joint: r_elbow_flex_joint.dof.limits.lower.position
                    - 0.2,
                    torso_lift_joint: torso_lift_joint.dof.limits.lower.position - 0.2,
                    head_pan_joint: head_pan_joint.dof.limits.lower.position - 0.2,
                }
            )
        )
        msc.add_node(min_joint_goal)
        min_joint_goal.success_condition = min_joint_goal.observes_true

        torso_joint_goal = JointPositionList(
            goal_state=JointState.from_mapping(mapping={torso_lift_joint: 3.2})
        )
        msc.add_node(torso_joint_goal)
        torso_joint_goal.start_condition = min_joint_goal.observes_true
        torso_joint_goal.success_condition = torso_joint_goal.observes_true

        max_joint_goal = JointPositionList(
            goal_state=JointState.from_mapping(
                mapping={
                    r_elbow_flex_joint: r_elbow_flex_joint.dof.limits.upper.position
                    + 0.2,
                    torso_lift_joint: torso_lift_joint.dof.limits.upper.position + 0.2,
                    head_pan_joint: head_pan_joint.dof.limits.upper.position + 0.2,
                }
            )
        )
        msc.add_node(max_joint_goal)
        max_joint_goal.start_condition = torso_joint_goal.observes_true

        end = EndMotion()
        msc.add_node(end)
        end.start_condition = max_joint_goal.observes_true
        giskard.api.compile(msc)
        giskard.api.execute()


class TestConstraints:

    def test_drive_into_apartment(self, apartment_setup: PR2Tester):
        msc = Statechart(context=apartment_setup.api.context)
        msc.add_node(
            cart_goal := CartesianPose(
                root_link=apartment_setup.map,
                tip_link=apartment_setup.base_footprint,
                goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0.4, y=-2.0, reference_frame=apartment_setup.base_footprint
                ),
            )
        )
        msc.add_node(EndMotion.when_true(cart_goal))
        apartment_setup.api.compile(msc)
        apartment_setup.api.execute()

    def test_insert_cylinder1(self, giskard_better_pose: PR2Tester):
        cylinder_name = "C"
        cylinder_height = 0.121
        hole_point = Point3(
            x=1.0, y=-1.0, z=0.5, reference_frame=giskard_better_pose.map
        )
        pose = HomogeneousTransformationMatrix.from_xyz_axis_angle(
            axis=Vector3.Y(),
            angle=pi / 2,
            reference_frame=giskard_better_pose.right_tip,
        )
        giskard_better_pose.add_cylinder_to_world(
            name=cylinder_name,
            height=cylinder_height,
            radius=0.0225,
            pose=pose,
            parent_link=giskard_better_pose.right_tip,
        )
        cylinder = giskard_better_pose.api.world.get_kinematic_structure_entity_by_name(
            cylinder_name
        )

        msc = Statechart(context=giskard_better_pose.api.context)
        msc.add_node(
            inserted := InsertCylinder(
                name="Insert Cylinder",
                tip_link=cylinder,
                tip_P_tool=Point3(z=cylinder_height / 2, reference_frame=cylinder),
                tip_V_axis=Vector3(z=-1.0, reference_frame=cylinder),
                up_axis=Vector3.Z(reference_frame=giskard_better_pose.map),
                hole_point=hole_point,
            )
        )
        msc.add_node(EndMotion.when_true(inserted))
        giskard_better_pose.api.compile(msc)
        giskard_better_pose.api.execute()

        map_T_cylinder = giskard_better_pose.api.world.compute_forward_kinematics(
            root=giskard_better_pose.map, tip=cylinder
        )
        map_V_cylinder_axis = map_T_cylinder.rotation_matrix.z_vector()
        map_P_leading_end = map_T_cylinder.position + map_V_cylinder_axis * (
            cylinder_height / 2
        )
        assert np.allclose(map_P_leading_end, hole_point, atol=0.02)
        assert np.allclose(map_V_cylinder_axis, Vector3(z=-1.0), atol=0.02)

    def test_pointing_kitchen(self, kitchen_setup: PR2Tester, better_pose):
        pointing_axis = Vector3.X(reference_frame=kitchen_setup.camera)
        gaya_pose2 = deepcopy(better_pose)
        del gaya_pose2[PR2Joint.HEAD_PAN]
        del gaya_pose2[PR2Joint.HEAD_TILT]

        handle_point = kitchen_setup.api.world.compute_forward_kinematics(
            root=kitchen_setup.map,
            tip=kitchen_setup.api.world.get_kinematic_structure_entity_by_name(
                "iai_fridge_door_handle"
            ),
        ).position

        msc = Statechart(context=kitchen_setup.api.context)
        msc.add_node(
            sequence := Sequence(
                [
                    Pointing(
                        root_link=kitchen_setup.map,
                        tip_link=kitchen_setup.camera,
                        goal_point=handle_point,
                        pointing_axis=pointing_axis,
                    ),
                    Parallel(
                        [
                            Pointing(
                                root_link=kitchen_setup.map,
                                tip_link=kitchen_setup.camera,
                                goal_point=handle_point,
                                pointing_axis=pointing_axis,
                            ),
                            CartesianPose(
                                root_link=kitchen_setup.map,
                                tip_link=kitchen_setup.base_footprint,
                                goal_pose=HomogeneousTransformationMatrix.from_xyz_axis_angle(
                                    y=2.0,
                                    axis=Vector3.Z(),
                                    angle=1,
                                    reference_frame=kitchen_setup.base_footprint,
                                ),
                            ),
                            JointPositionList(
                                goal_state=JointState.from_str_dict(
                                    gaya_pose2, world=kitchen_setup.api.world
                                )
                            ),
                        ]
                    ),
                ]
            )
        )
        msc.add_node(EndMotion.when_true(sequence))
        kitchen_setup.api.compile(msc)
        kitchen_setup.api.execute()

        msc = Statechart(context=kitchen_setup.api.context)
        msc.add_node(
            parallel := Parallel(
                [
                    Pointing(
                        root_link=kitchen_setup.right_tip,
                        tip_link=kitchen_setup.camera,
                        goal_point=Point3(reference_frame=kitchen_setup.right_tip),
                        pointing_axis=pointing_axis,
                    ),
                    CartesianPose(
                        root_link=kitchen_setup.base_footprint,
                        tip_link=kitchen_setup.right_tip,
                        goal_pose=HomogeneousTransformationMatrix.from_point_rotation_matrix(
                            point=Point3(x=-0.3, z=0.6),
                            rotation_matrix=RotationMatrix(
                                [
                                    [0, 0, -1, 0],
                                    [0, 1, 0, 0],
                                    [1, 0, 0, 0],
                                    [0, 0, 0, 1],
                                ]
                            ),
                            reference_frame=kitchen_setup.right_tip,
                        ),
                    ),
                ]
            ),
        )
        msc.add_node(EndMotion.when_true(parallel))
        kitchen_setup.api.compile(msc)
        kitchen_setup.api.execute()

    def test_align_planes1(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            parallel := Parallel(
                [
                    AlignPlanes(
                        root_link=giskard.map,
                        tip_link=giskard.right_tip,
                        tip_normal=Vector3.X(reference_frame=giskard.right_tip),
                        goal_normal=Vector3.X(reference_frame=giskard.map),
                    ),
                    AlignPlanes(
                        root_link=giskard.map,
                        tip_link=giskard.right_tip,
                        tip_normal=Vector3.Y(reference_frame=giskard.right_tip),
                        goal_normal=Vector3.Z(reference_frame=giskard.map),
                    ),
                ]
            )
        )
        msc.add_node(EndMotion.when_true(parallel))

        giskard.api.compile(msc)
        giskard.api.execute()


class TestCartGoals:

    def test_cart_goal_1eef(self, giskard: PR2Tester):
        tip = giskard.api.world.get_kinematic_structure_entity_by_name(
            "r_gripper_tool_frame"
        )
        root = giskard.api.world.get_kinematic_structure_entity_by_name(
            "base_footprint"
        )
        tip_goal = HomogeneousTransformationMatrix.from_xyz_quaternion(
            pos_x=-0.2, reference_frame=tip
        )

        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            cart_goal := CartesianPose(
                root_link=root,
                tip_link=tip,
                goal_pose=tip_goal,
            )
        )
        msc.add_node(EndMotion.when_true(cart_goal))
        giskard.api.compile(msc)
        giskard.api.execute()

    def test_cart_goal_unreachable(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            cart_goal := CartesianPose(
                root_link=giskard.map,
                tip_link=giskard.base_footprint,
                goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                    z=-1,
                    reference_frame=giskard.map,
                ),
            )
        )
        msc.add_node(local_min := LocalMinimumReached())
        msc.add_node(CancelStatechart.when_true(cart_goal))
        msc.add_node(EndMotion.when_true(local_min))
        giskard.api.compile(msc)
        giskard.api.execute()

    def test_cart_goal_orientation_singularity(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            parallel := Parallel(
                [
                    CartesianPose(
                        root_link=giskard.base_link,
                        tip_link=giskard.right_tip,
                        goal_pose=HomogeneousTransformationMatrix.from_xyz_quaternion(
                            pos_x=-0.1,
                            reference_frame=giskard.right_tip,
                        ),
                    ),
                    CartesianPose(
                        root_link=giskard.base_link,
                        tip_link=giskard.left_tip,
                        goal_pose=HomogeneousTransformationMatrix.from_xyz_quaternion(
                            pos_x=-0.05,
                            reference_frame=giskard.left_tip,
                        ),
                    ),
                ]
            )
        )
        msc.add_node(EndMotion.when_true(parallel))
        giskard.api.compile(msc)
        giskard.api.execute()

    def test_cart_goal_left_right_chain(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            cart_goal := CartesianPose(
                root_link=giskard.left_tip,
                tip_link=giskard.right_tip,
                goal_pose=HomogeneousTransformationMatrix.from_point_rotation_matrix(
                    point=Point3(
                        0.2,
                        0.0,
                        reference_frame=giskard.left_tip,
                    ),
                    rotation_matrix=RotationMatrix(
                        [[-1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1.0]],
                        reference_frame=giskard.left_tip,
                    ),
                    reference_frame=giskard.left_tip,
                ),
            )
        )
        msc.add_node(EndMotion.when_true(cart_goal))
        giskard.api.compile(msc)
        giskard.api.execute()

    def test_root_link_not_equal_chain_root(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            cart_goal := CartesianPose(
                root_link=giskard.torso_lift_link,
                tip_link=giskard.right_tip,
                goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0.8,
                    y=-0.5,
                    z=1.0,
                    reference_frame=giskard.base_footprint,
                ),
            )
        )
        msc.add_node(EndMotion.when_true(cart_goal))
        giskard.api.compile(msc)
        giskard.api.execute()


class TestSelfCollisionAvoidance:

    def test_cable_guide_collision(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_nodes(
            [
                joint_goal := JointPositionList(
                    goal_state=JointState.from_str_dict(
                        {PR2Joint.HEAD_PAN: 2.84, PR2Joint.HEAD_TILT: 1.0},
                        world=giskard.api.world,
                    )
                ),
                SelfCollisionAvoidance(),
                local_min := LocalMinimumReached(),
            ]
        )
        msc.add_node(EndMotion.when_true(local_min))
        giskard.api.compile(msc)
        giskard.api.execute()
        assert joint_goal.observation_state == ObservationStateValues.FALSE

    def test_attached_self_collision_avoid_stick(self, giskard: PR2Tester):
        collision_pose = {
            PR2Joint.LEFT_ELBOW_FLEX: -1.1343683863086362,
            PR2Joint.LEFT_FOREARM_ROLL: 7.517553513504836,
            PR2Joint.LEFT_SHOULDER_LIFT: 0.5726770101613905,
            PR2Joint.LEFT_SHOULDER_PAN: 0.1592669164939349,
            PR2Joint.LEFT_UPPER_ARM_ROLL: 0.5532568387077381,
            PR2Joint.LEFT_WRIST_FLEX: -1.215660155912625,
            PR2Joint.LEFT_WRIST_ROLL: 4.249300323527076,
            PR2Joint.TORSO_LIFT: 0.2,
        }

        msc = Statechart(context=giskard.api.context)
        msc.add_nodes(
            [
                joint_goal := JointPositionList(
                    goal_state=JointState.from_str_dict(
                        collision_pose,
                        world=giskard.api.world,
                    )
                ),
            ]
        )
        msc.add_node(EndMotion.when_true(joint_goal))
        giskard.api.compile(msc)
        giskard.api.execute()

        attached_link_name = "pocky"
        giskard.add_box_to_world(
            name=attached_link_name,
            size=(0.16, 0.04, 0.04),
            parent_link=giskard.left_tip,
            pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.04, reference_frame=giskard.left_tip
            ),
        )

        msc = Statechart(context=giskard.api.context)
        msc.add_nodes(
            [
                JointPositionList(
                    goal_state=JointState.from_str_dict(
                        {
                            PR2Joint.RIGHT_FOREARM_ROLL: 0.0,
                            PR2Joint.RIGHT_SHOULDER_LIFT: 0.0,
                            PR2Joint.RIGHT_SHOULDER_PAN: 0.0,
                            PR2Joint.RIGHT_UPPER_ARM_ROLL: 0.0,
                            PR2Joint.RIGHT_WRIST_FLEX: -0.10001,
                            PR2Joint.RIGHT_WRIST_ROLL: 0.0,
                            PR2Joint.RIGHT_ELBOW_FLEX: -0.15,
                            PR2Joint.TORSO_LIFT: 0.2,
                        },
                        world=giskard.api.world,
                    )
                ),
                cart_goal := CartesianPose(
                    root_link=giskard.map,
                    tip_link=giskard.left_tip,
                    goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                        z=0.2, reference_frame=giskard.left_tip
                    ),
                ),
                SelfCollisionAvoidance(),
            ]
        )
        msc.add_node(EndMotion.when_true(cart_goal))
        giskard.api.compile(msc)
        giskard.api.execute()

        giskard.check_cpi_geq(giskard.get_l_gripper_links(), 0.048)
        giskard.check_cpi_geq(
            [
                giskard.api.world.get_kinematic_structure_entity_by_name(
                    attached_link_name
                )
            ],
            0.048,
        )

    def test_box_overlapping_with_gripper(self, giskard_better_pose: PR2Tester):
        box_name = "muh"
        giskard_better_pose.add_box_to_world(
            name=box_name,
            size=(0.2, 0.1, 0.1),
            pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.05, reference_frame=giskard_better_pose.right_tip
            ),
            parent_link=giskard_better_pose.right_tip,
        )
        box = giskard_better_pose.api.world.get_kinematic_structure_entity_by_name(
            box_name
        )

        msc = Statechart(context=giskard_better_pose.api.context)
        msc.add_nodes(
            [
                cart_goal := CartesianPose(
                    root_link=giskard_better_pose.map,
                    tip_link=box,
                    goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                        x=-0.5, reference_frame=box
                    ),
                ),
                SelfCollisionAvoidance(robot=giskard_better_pose.api.robot),
            ]
        )
        msc.add_node(EndMotion.when_true(cart_goal))
        msc.add_node(timeout := CountSimulationTimeSeconds(seconds=10))
        msc.add_node(CancelStatechart.when_true(timeout))
        giskard_better_pose.api.compile(msc)
        giskard_better_pose.api.execute()

    def test_avoid_self_collision_with_l_arm(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_nodes(
            [
                sequence := Sequence(
                    [
                        SetSeedConfiguration(
                            seed_configuration=JointState.from_str_dict(
                                {
                                    PR2Joint.RIGHT_ELBOW_FLEX: -1.43286344265,
                                    PR2Joint.RIGHT_FOREARM_ROLL: -1.26465060073,
                                    PR2Joint.RIGHT_SHOULDER_LIFT: 0.47990329056,
                                    PR2Joint.RIGHT_SHOULDER_PAN: -0.281272240139,
                                    PR2Joint.RIGHT_UPPER_ARM_ROLL: -0.528415402668,
                                    PR2Joint.RIGHT_WRIST_FLEX: -1.18811419869,
                                    PR2Joint.RIGHT_WRIST_ROLL: 2.26884630124,
                                },
                                world=giskard.api.world,
                            )
                        ),
                        CartesianPose(
                            root_link=giskard.base_footprint,
                            tip_link=giskard.right_tip,
                            goal_pose=Pose.from_xyz_rpy(
                                0.2, reference_frame=giskard.right_tip
                            ),
                        ),
                    ]
                ),
                SelfCollisionAvoidance(robot=giskard.api.robot),
            ]
        )

        msc.add_node(EndMotion.when_true(sequence))

        giskard.api.compile(msc)
        giskard.api.execute()
        giskard.check_cpi_geq(giskard.get_r_gripper_links(), 0.048)

    def test_avoid_self_collision_specific_link(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_nodes(
            [
                sequence := Sequence(
                    [
                        SetSeedConfiguration(
                            seed_configuration=JointState.from_str_dict(
                                {
                                    PR2Joint.RIGHT_SHOULDER_PAN: -0.0672581793019,
                                    PR2Joint.RIGHT_SHOULDER_LIFT: 0.429650469244,
                                    PR2Joint.RIGHT_UPPER_ARM_ROLL: -0.580889703636,
                                    PR2Joint.RIGHT_FOREARM_ROLL: -101.948215412,
                                    PR2Joint.RIGHT_ELBOW_FLEX: -1.35221928696,
                                    PR2Joint.RIGHT_WRIST_FLEX: -0.986144640142,
                                    PR2Joint.RIGHT_WRIST_ROLL: 0.7397216172451033,
                                },
                                world=giskard.api.world,
                            )
                        ),
                        CartesianPose(
                            root_link=giskard.base_footprint,
                            tip_link=giskard.right_tip,
                            goal_pose=Pose.from_xyz_rpy(
                                0.2, reference_frame=giskard.right_tip
                            ),
                        ),
                    ]
                ),
                UpdateTemporaryCollisionRules(
                    temporary_rules=[
                        AvoidCollisionBetweenGroups(
                            buffer_zone_distance=0.05,
                            body_group_a=list(giskard.get_r_gripper_links()),
                            body_group_b=[
                                giskard.api.world.get_kinematic_structure_entity_by_name(
                                    "l_forearm_link"
                                )
                            ],
                        )
                    ]
                ),
                SelfCollisionAvoidance(robot=giskard.api.robot),
            ]
        )

        msc.add_node(EndMotion.when_true(sequence))
        giskard.api.compile(msc)
        giskard.api.execute()

        giskard.check_cpi_geq(giskard.get_r_gripper_links(), 0.048)

    def test_get_out_of_self_collision(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            sequence := Sequence(
                [
                    JointPositionList(
                        goal_state=JointState.from_str_dict(
                            {
                                PR2Joint.LEFT_ELBOW_FLEX: -1.43286344265,
                                PR2Joint.LEFT_FOREARM_ROLL: 1.26465060073,
                                PR2Joint.LEFT_SHOULDER_LIFT: 0.47990329056,
                                PR2Joint.LEFT_SHOULDER_PAN: 0.281272240139,
                                PR2Joint.LEFT_UPPER_ARM_ROLL: 0.528415402668,
                                PR2Joint.LEFT_WRIST_FLEX: -1.18811419869,
                                PR2Joint.LEFT_WRIST_ROLL: 2.26884630124,
                            },
                            world=giskard.api.world,
                        )
                    ),
                    CartesianPose(
                        root_link=giskard.base_footprint,
                        tip_link=giskard.left_tip,
                        goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                            0.15, reference_frame=giskard.left_tip
                        ),
                    ),
                ]
            )
        )
        msc.add_node(EndMotion.when_true(sequence))
        giskard.api.compile(msc)
        giskard.api.execute()

        msc = Statechart(context=giskard.api.context)
        msc.add_nodes(
            [
                SelfCollisionAvoidance(robot=giskard.api.robot),
                local_min := LocalMinimumReached(),
            ]
        )
        msc.add_node(EndMotion.when_true(local_min))
        with pytest.raises(CollisionViolatedError):
            giskard.api.compile(msc)
            giskard.api.execute()


class TestCollisionAvoidanceGoals:

    def test_hard_constraints_violated(self, kitchen_setup: PR2Tester):
        msc = Statechart(context=kitchen_setup.api.context)
        msc.add_node(
            Sequence(
                [
                    SetOdometry(
                        base_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                            x=2.0, reference_frame=kitchen_setup.map
                        )
                    ),
                    ExternalCollisionAvoidance(),
                ]
            )
        )
        with pytest.raises(CollisionViolatedError):
            kitchen_setup.api.compile(msc)
            kitchen_setup.api.execute()

    def test_avoid_collision_go_around_corner(self, fake_table_setup: PR2Tester):
        msc = Statechart(context=fake_table_setup.api.context)

        cart_goal = CartesianPose(
            root_link=fake_table_setup.default_root,
            tip_link=fake_table_setup.right_tip,
            goal_pose=cas.Pose.from_xyz_axis_angle(
                x=0.8,
                y=-0.38,
                z=0.84,
                axis=cas.Vector3.Y(),
                angle=np.pi / 2.0,
                reference_frame=fake_table_setup.default_root,
            ),
        )
        msc.add_node(cart_goal)

        msc.add_node(
            UpdateTemporaryCollisionRules(
                temporary_rules=[
                    AvoidExternalCollisions(
                        buffer_zone_distance=0.1,
                        violated_distance=0.0,
                        robot=fake_table_setup.api.robot,
                    )
                ]
            )
        )
        msc.add_node(ExternalCollisionAvoidance(robot=fake_table_setup.api.robot))
        msc.add_node(local_min := LocalMinimumReached())
        msc.add_node(EndMotion.when_true(local_min))

        fake_table_setup.api.compile(msc)
        fake_table_setup.api.execute()
        fake_table_setup.check_cpi_geq(fake_table_setup.get_l_gripper_links(), 0.05)
        fake_table_setup.check_cpi_geq(
            [
                fake_table_setup.giskard.executor.context.world.get_kinematic_structure_entity_by_name(
                    "r_gripper_l_finger_tip_link"
                )
            ],
            0.045,
        )
        fake_table_setup.check_cpi_geq(
            [
                fake_table_setup.giskard.executor.context.world.get_kinematic_structure_entity_by_name(
                    "r_gripper_r_finger_tip_link"
                )
            ],
            0.045,
        )

    def test_avoid_collision_box_between_3_boxes(self, pocky_pose_setup: PR2Tester):
        r_tip = pocky_pose_setup.right_tip
        poses_relative_to_r_tip = {
            "box": HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.08, reference_frame=r_tip
            ),
            "b1": HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.2, reference_frame=r_tip
            ),
            "bl": HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.15, y=0.04, reference_frame=r_tip
            ),
            "br": HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.15, y=-0.04, reference_frame=r_tip
            ),
        }
        pocky_pose_setup.add_box_to_world(
            name="box",
            size=(0.2, 0.05, 0.05),
            parent_link=r_tip,
            pose=poses_relative_to_r_tip["box"],
        )
        pocky_pose_setup.add_box_to_world(
            "b1", (0.01, 0.2, 0.2), pose=poses_relative_to_r_tip["b1"]
        )
        pocky_pose_setup.add_box_to_world(
            "bl", (0.1, 0.01, 0.2), pose=poses_relative_to_r_tip["bl"]
        )
        pocky_pose_setup.add_box_to_world(
            "br", (0.1, 0.01, 0.2), pose=poses_relative_to_r_tip["br"]
        )

        # The obstacles are placed relative to the gripper, so a world that is behind on
        # the state of the robot scatters them somewhere else entirely and leaves the
        # gripper nothing to avoid.
        server_world = pocky_pose_setup.world
        server_r_tip = server_world.get_kinematic_structure_entity_by_name(
            "r_gripper_tool_frame"
        )
        for name, pose in poses_relative_to_r_tip.items():
            body = server_world.get_kinematic_structure_entity_by_name(name)
            compare_points(
                actual_point=server_world.compute_forward_kinematics(
                    server_r_tip, body
                ).position,
                desired_point=pose.position,
                decimal=4,
            )

        box = pocky_pose_setup.api.world.get_kinematic_structure_entity_by_name("box")

        msc = Statechart(context=pocky_pose_setup.api.context)
        msc.add_nodes(
            [
                AlignPlanes(
                    root_link=pocky_pose_setup.map,
                    tip_link=box,
                    tip_normal=Vector3.X(reference_frame=box),
                    goal_normal=Vector3.X(reference_frame=pocky_pose_setup.map),
                ),
                AlignPlanes(
                    root_link=pocky_pose_setup.map,
                    tip_link=box,
                    tip_normal=Vector3.Y(reference_frame=box),
                    goal_normal=Vector3.Y(reference_frame=pocky_pose_setup.map),
                ),
                ExternalCollisionAvoidance(),
                local_min := LocalMinimumReached(),
            ]
        )
        msc.add_node(EndMotion.when_true(local_min))

        pocky_pose_setup.api.compile(msc)
        pocky_pose_setup.api.execute()
        pocky_pose_setup.check_cpi_geq(pocky_pose_setup.get_r_gripper_links(), 0.04)

    def test_attached_two_items(self, giskard: PR2Tester):
        box1_name = "box1"
        box2_name = "box2"

        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            node := Sequence(
                [
                    JointPositionList(
                        goal_state=JointState.from_str_dict(
                            {
                                PR2Joint.RIGHT_ELBOW_FLEX: -1.58118094489,
                                PR2Joint.RIGHT_FOREARM_ROLL: -0.904933033043,
                                PR2Joint.RIGHT_SHOULDER_LIFT: 0.822412440711,
                                PR2Joint.RIGHT_SHOULDER_PAN: -1.07866800992,
                                PR2Joint.RIGHT_UPPER_ARM_ROLL: -1.34905471854,
                                PR2Joint.RIGHT_WRIST_FLEX: -1.20182042644,
                                PR2Joint.RIGHT_WRIST_ROLL: 0.190433188769,
                            },
                            world=giskard.api.world,
                        )
                    ),
                    CartesianPose(
                        root_link=giskard.torso_lift_link,
                        tip_link=giskard.left_tip,
                        goal_pose=HomogeneousTransformationMatrix.from_point_rotation_matrix(
                            point=Point3(x=0.4),
                            rotation_matrix=RotationMatrix(
                                [
                                    [-1, 0, 0, 0],
                                    [0, 1, 0, 0],
                                    [0, 0, -1, 0],
                                    [0, 0, 0, 1.0],
                                ]
                            ),
                            reference_frame=giskard.right_tip,
                        ),
                    ),
                ]
            )
        )
        msc.add_node(EndMotion.when_true(node))
        giskard.api.compile(msc)
        giskard.api.execute()

        giskard.add_box_to_world(
            box1_name,
            size=(0.2, 0.04, 0.04),
            parent_link=giskard.right_tip,
            pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.1, reference_frame=giskard.right_tip
            ),
        )
        giskard.add_box_to_world(
            box2_name,
            size=(0.2, 0.04, 0.04),
            parent_link=giskard.left_tip,
            pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.1, reference_frame=giskard.left_tip
            ),
        )
        msc = Statechart(context=giskard.api.context)
        msc.add_nodes(
            [
                SelfCollisionAvoidance(robot=giskard.api.robot),
                local_min := LocalMinimumReached(),
            ]
        )
        msc.add_node(EndMotion.when_true(local_min))
        giskard.api.compile(msc)
        giskard.api.execute()

        giskard.check_cpi_geq(
            [
                giskard.api.world.get_kinematic_structure_entity_by_name(box1_name),
                giskard.api.world.get_kinematic_structure_entity_by_name(box2_name),
            ],
            0.049,
        )

        # assert (
        #     god_map.debug_expression_manager.evaluated_debug_expressions[
        #         PrefixedName(name=f"mIndex {giskard.r_tip}", prefix="")
        #     ][0]
        #     >= m_threshold - 0.02
        # )
        # assert (
        #     god_map.debug_expression_manager.evaluated_debug_expressions[
        #         PrefixedName(name=f"mIndex {giskard.l_tip}", prefix="")
        #     ][0]
        #     >= m_threshold - 0.02
        # )


class TestActionServerEvents:
    def test_wrong_params1(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            joint_goal := JointPositionList(
                goal_state=HomogeneousTransformationMatrix(),
            )
        )
        msc.add_node(EndMotion.when_true(joint_goal))
        with pytest.raises(AttributeError):
            giskard.api.compile(msc)
            giskard.api.execute()

        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            joint_goal := JointPositionList(
                goal_state=JointState.from_str_dict(
                    giskard.better_pose_left, world=giskard.api.world
                ),
            )
        )
        msc.add_node(EndMotion.when_true(joint_goal))
        giskard.api.compile(msc)
        giskard.api.execute()

    @pytest.mark.asyncio
    async def test_cancel_with_new_goal(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            CartesianPose(
                root_link=giskard.map,
                tip_link=giskard.base_footprint,
                goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=100, reference_frame=giskard.base_footprint
                ),
            )
        )

        giskard.api.compile(msc)
        goal_accepted_future = giskard.api.execute_async()
        wait_for_future_to_complete(goal_accepted_future)

        await asyncio.sleep(2)

        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            cart_goal := CartesianPose(
                root_link=giskard.map,
                tip_link=giskard.base_footprint,
                goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                    y=1, reference_frame=giskard.base_footprint
                ),
            )
        )
        msc.add_node(EndMotion.when_true(cart_goal))

        giskard.api.compile(msc)
        goal_accepted_future = giskard.api.execute_async()
        wait_for_future_to_complete(goal_accepted_future)

        await giskard.api.get_result()

    @pytest.mark.asyncio
    async def test_interrupt(self, giskard: PR2Tester):
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            CartesianPose(
                root_link=giskard.map,
                tip_link=giskard.base_footprint,
                goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0.5, reference_frame=giskard.base_footprint
                ),
            )
        )

        giskard.api.compile(msc)
        goal_accepted_future = giskard.api.execute_async()
        wait_for_future_to_complete(goal_accepted_future)

        await asyncio.sleep(2)
        wait_for_future_to_complete(giskard.api.cancel_goal_async())

        with pytest.raises(ExecutionCanceledException):
            await giskard.api.get_result()

    @pytest.mark.asyncio
    async def test_a_goal_whose_client_stops_announcing_itself_is_aborted(
        self, giskard: PR2Tester
    ):
        """
        Nobody is waiting for a motion whose client died, so it is stopped instead of
        being driven to its end.

        The motion ends by itself after a while, so that a client that is not noticed
        leaving fails this test instead of keeping the goal running forever.
        """
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            CartesianPose(
                root_link=giskard.map,
                tip_link=giskard.base_footprint,
                goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0.5, reference_frame=giskard.base_footprint
                ),
            )
        )
        msc.add_node(give_up := CountSeconds(seconds=30))
        msc.add_node(EndMotion.when_true(give_up))
        giskard.api.compile(msc)
        goal_accepted_future = giskard.api.execute_async()
        wait_for_future_to_complete(goal_accepted_future)
        client_watchdog = giskard.giskard.motion_server.client_watchdog
        assert wait_until(
            lambda: client_watchdog.presence.watched_client == giskard.api.client,
            timeout=30.0,
        )

        giskard.api.heartbeat_publisher.stop()

        with pytest.raises(ClientDisconnectedError) as disconnect:
            await giskard.api.get_result()
        assert disconnect.value.client == giskard.api.client

    def test_empty_goal(self, giskard: PR2Tester):
        giskard.api.compile(Statechart(context=giskard.api.context))
        with pytest.raises(EmptyStatechartError):
            giskard.api.execute()

    @pytest.mark.asyncio
    async def test_world_model_modification_terminates_the_motion(
        self, giskard: PR2Tester
    ):
        """
        The running motion was compiled against the structure of the world, so a body
        added by another process ends it instead of being applied underneath it.
        """
        msc = Statechart(context=giskard.api.context)
        msc.add_node(
            CartesianPose(
                root_link=giskard.map,
                tip_link=giskard.base_footprint,
                goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0.5, reference_frame=giskard.base_footprint
                ),
            )
        )

        giskard.api.compile(msc)
        goal_accepted_future = giskard.api.execute_async()
        wait_for_future_to_complete(goal_accepted_future)

        await asyncio.sleep(1)

        giskard.add_box_to_world(
            name="box",
            size=(0.05, 0.01, 0.15),
            pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                z=0.06, reference_frame=giskard.right_tip
            ),
            parent_link=giskard.right_tip,
        )

        with pytest.raises(WorldModelModifiedDuringMotionError):
            await giskard.api.get_result()

        await asyncio.sleep(1)

        # the modification is applied once the motion is over
        assert giskard.api.world.get_kinematic_structure_entity_by_name("box")
        assert giskard.giskard.executor.context.world.get_kinematic_structure_entity_by_name(
            "box"
        )


# kernprof -lv py.test -s test/test_integration_pr2.py


# kernprof -lv py.test -s test/test_integration_pr2.py
# time: [1-9][1-9]*.[1-9]* s
# import pytest
# pytest.main(['-s', __file__ + '::TestManipulability::test_manip1'])
# pytest.main(['-s', __file__ + '::TestJointGoals::test_joint_goal'])
# pytest.main(['-s', __file__ + '::TestConstraints::test_RelativePositionSequence'])
# pytest.main(['-s', __file__ + '::TestConstraints::test_open_dishwasher_apartment'])
# pytest.main(['-s', __file__ + '::TestCollisionAvoidanceGoals::test_bowl_and_cup'])
# pytest.main(['-s', __file__ + '::TestMonitors::test_joint_and_base_goal'])
# pytest.main(['-s', __file__ + '::TestCollisionAvoidanceGoals::test_avoid_collision_go_around_corner'])
# pytest.main(['-s', __file__ + '::TestCollisionAvoidanceGoals::test_avoid_collision_box_between_boxes'])
# pytest.main(['-s', __file__ + '::TestSelfCollisionAvoidance::test_avoid_self_collision_with_l_arm'])
# pytest.main(['-s', __file__ + '::TestCollisionAvoidanceGoals::test_avoid_collision_at_kitchen_corner'])
# pytest.main(['-s', __file__ + '::TestWayPoints::test_waypoints2'])
# pytest.main(['-s', __file__ + '::TestCartGoals::test_10_cart_goals'])
# pytest.main(['-s', __file__ + '::TestCartGoals::test_cart_goal_2eef2'])
# pytest.main(['-s', __file__ + '::TestWorld::test_compute_self_collision_matrix'])

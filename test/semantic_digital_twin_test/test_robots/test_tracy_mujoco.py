"""
Tests for mounting Tracy into a world and simulating it physically in MuJoCo; skipped
where Tracy's description is not installed.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from ...pytest_environment import runs_in_continuous_integration

from semantic_digital_twin.adapters.multi_sim import MujocoBuilder, MujocoSim
from semantic_digital_twin.api import RobotSpecification
from semantic_digital_twin.datastructures.definitions import StaticJointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy, TracyJoint
from semantic_digital_twin.semantic_annotations.semantic_annotations import Table
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.utils import tracy_installed
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import (
    Body,
    GravityCompensation,
)

pytestmark = pytest.mark.skipif(
    not tracy_installed(), reason="iai_tracy_description is not installed"
)


@pytest.fixture
def mounted_tracy() -> Tracy:
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
    return RobotSpecification(Tracy).spawn(world)


def test_a_stationary_robot_is_bolted_to_the_world_through_a_fixed_odom():
    """
    Tracy has no mobile base, so both its odom and its drive are fixed connections, and
    the localization pose it is spawned with is where its root ends up.
    """
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
    world_T_odom = HomogeneousTransformationMatrix.from_xyz_rpy(x=1.0, y=2.0)

    tracy = RobotSpecification(Tracy, world_T_odom=world_T_odom).spawn(world)

    odom_C_robot = tracy.root.parent_connection.parent.parent_connection
    root_C_odom = odom_C_robot.parent.parent_connection
    assert isinstance(odom_C_robot, FixedConnection)
    assert isinstance(root_C_odom, FixedConnection)
    assert root_C_odom.parent is world.root
    root_position = world.compute_forward_kinematics_np(world.root, tracy.root)[:3, 3]
    assert root_position[:2] == pytest.approx([1.0, 2.0])


def test_the_mounting_table_is_a_table_at_the_robots_root(mounted_tracy):
    """
    The table the arms are bolted onto is a robot part of its own, so it is set up with
    the robot, and a table, so its top is where objects can stand.
    """
    table = mounted_tracy.table

    assert isinstance(table, Table)
    assert table.root is mounted_tracy.root
    assert table in mounted_tracy._robot_parts
    widest_slab = max(
        table.root.collision.as_bounding_box_collection_in_frame(
            mounted_tracy._world.root
        ),
        key=lambda box: (box.max_x - box.min_x) * (box.max_y - box.min_y),
    )
    assert table.top_z == pytest.approx(widest_slab.max_z)


def test_every_arm_and_gripper_joint_is_servoed_on_mounting(mounted_tracy, tmp_path):
    """
    A mounted Tracy declares each arm and gripper joint's own servo, so the compiled
    model drives every one of those degrees of freedom with a servo.
    """
    world = mounted_tracy._world
    shoulder = world.get_connection_by_name(TracyJoint.LEFT_SHOULDER_PAN)
    knuckle = world.get_connection_by_name(TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE)
    gripper = mounted_tracy.left_arm.end_effector

    expected_shoulder = mounted_tracy.left_arm.servos_by_joint["shoulder_pan_joint"]
    assert shoulder.raw_dof.servo_gains == expected_shoulder.gains
    assert shoulder.dynamics == expected_shoulder.dynamics
    assert knuckle.raw_dof.servo_gains == gripper.finger_servo.gains
    assert knuckle.dynamics == gripper.finger_servo.dynamics

    builder = MujocoBuilder()
    builder.build_world(world=world, file_path=str(tmp_path / "scene.xml"))
    servoed_degrees_of_freedom = {
        connection.raw_dof.name.name
        for arm in mounted_tracy.get_arms()
        for connection in arm.active_connections + arm.end_effector.active_connections
    }
    assert {
        actuator.target for actuator in builder.spec.actuators
    } == servoed_degrees_of_freedom
    assert TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE in servoed_degrees_of_freedom


def test_mounting_alone_leaves_the_descriptions_own_finger_velocity_limit(
    mounted_tracy,
):
    """
    Kinematic planning against a Tracy that is never physically simulated has no reason
    to distrust the description's own, conservative velocity limit.
    """
    knuckle = mounted_tracy._world.get_connection_by_name(
        TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE
    )
    gripper = mounted_tracy.left_arm.end_effector

    assert knuckle.raw_dof.limits.upper.velocity != gripper.finger_velocity_limit


def test_preparing_for_physical_simulation_overwrites_the_finger_velocity_limit(
    mounted_tracy,
):
    mounted_tracy.prepare_for_physical_simulation()

    gripper = mounted_tracy.left_arm.end_effector
    knuckle = mounted_tracy._world.get_connection_by_name(
        TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE
    )

    assert knuckle.raw_dof.limits.upper.velocity == gripper.finger_velocity_limit
    assert knuckle.raw_dof.limits.lower.velocity == -gripper.finger_velocity_limit


def test_the_servoed_parts_carry_their_weight_and_the_links_pass_through_each_other(
    mounted_tracy, tmp_path
):
    """
    Every arm and gripper link is gravity-compensated, and the compiled model excludes
    contacts between the robot's own links while the fingers keep colliding with the
    table they may press into.

    Pairs the description itself lists as adjacent, such as the table and the arm bases
    mounted on it, stay excluded.
    """
    for arm in mounted_tracy.get_arms():
        for body in arm.bodies + arm.end_effector.bodies:
            assert body.get_simulator_property_of_type(GravityCompensation) == (
                GravityCompensation(fraction=1.0)
            )
    builder = MujocoBuilder()
    builder.build_world(
        world=mounted_tracy._world, file_path=str(tmp_path / "scene.xml")
    )
    excluded_pairs = {
        frozenset((exclude.bodyname1, exclude.bodyname2))
        for exclude in builder.spec.excludes
    }
    fingertip = mounted_tracy.left_arm.end_effector.left_fingertip.name.name
    wrist = mounted_tracy._world.get_connection_by_name(
        TracyJoint.LEFT_WRIST_3
    ).child.name.name
    table = mounted_tracy.root.name.name
    assert frozenset((fingertip, wrist)) in excluded_pairs
    assert frozenset((fingertip, table)) not in excluded_pairs


@pytest.mark.skipif(
    not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
)
def test_the_servos_hold_the_parked_arms_up(mounted_tracy):
    """
    A joint with no servo would be written straight into MuJoCo and sag under its own
    weight between one control cycle and the next.
    """
    world = mounted_tracy._world
    for arm in mounted_tracy.get_arms():
        arm.get_joint_state_by_type(StaticJointState.PARK).apply_to(world)
    world.notify_state_change()
    tool_frame = mounted_tracy.left_arm.end_effector.tool_frame
    parked = world.compute_forward_kinematics_np(world.root, tool_frame)[:3, 3]

    simulation = MujocoSim(world=world, headless=True)
    simulation.start_stepped_simulation()
    try:
        simulation.step_simulation(timedelta(seconds=1))
        simulated = simulation.simulator.get_body_position(
            body_name=tool_frame.name.name
        ).result
    finally:
        simulation.stop_simulation()

    assert list(simulated) == pytest.approx(list(parked), abs=0.01)


# %% the gripper's own geometry


def test_gripper_geometry_names_the_pads_and_the_driving_joint(mounted_tracy):
    gripper = mounted_tracy.left_arm.end_effector

    assert gripper.left_fingertip.name.name == "left_robotiq_85_left_finger_tip_link"
    assert gripper.right_fingertip.name.name == "left_robotiq_85_right_finger_tip_link"
    assert gripper.knuckle_joint.name.name == TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE
    assert (
        mounted_tracy.right_arm.end_effector.knuckle_joint.name.name
        == TracyJoint.RIGHT_GRIPPER_LEFT_KNUCKLE
    )


def test_knuckle_angle_closes_the_pads_to_a_width_between_open_and_closed(
    mounted_tracy,
):
    """
    A width the open gripper already spans needs no closing, a width the closed gripper
    still spans needs the full close, and one in between is found by bisection, with a
    wider target closing less, and leaves the world untouched.
    """
    gripper = mounted_tracy.left_arm.end_effector
    limits = gripper.knuckle_joint.raw_dof.limits
    open_angle, closed_angle = limits.lower.position, limits.upper.position
    state_before = mounted_tracy._world.state[gripper.knuckle_joint.raw_dof.id].position

    narrow = gripper.knuckle_angle_for_half_width(0.02)
    wide = gripper.knuckle_angle_for_half_width(0.03)

    assert gripper.knuckle_angle_for_half_width(1.0) == open_angle
    assert gripper.knuckle_angle_for_half_width(0.0) == closed_angle
    assert open_angle < wide < narrow < closed_angle
    assert (
        mounted_tracy._world.state[gripper.knuckle_joint.raw_dof.id].position
        == state_before
    )

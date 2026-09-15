"""
Tests for mounting Tracy into a world and equipping it for physical simulation in
MuJoCo; skipped where Tracy's description is not installed.
"""

from __future__ import annotations


import pytest

from ...pytest_environment import runs_in_continuous_integration

from semantic_digital_twin.adapters.multi_sim import MujocoBody, MujocoBuilder
from semantic_digital_twin.adapters.mujoco_tuning import equip_for_mujoco
from semantic_digital_twin.adapters.real_time_simulation import RealTimeSimulation
from semantic_digital_twin.datastructures.definitions import StaticJointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy, TracyJoint
from semantic_digital_twin.utils import tracy_installed
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

pytestmark = pytest.mark.skipif(
    not tracy_installed(), reason="iai_tracy_description is not installed"
)


@pytest.fixture
def mounted_tracy() -> Tracy:
    tracy_world = Tracy.parse_description()
    mount_pose = Tracy.floor_mount_pose(tracy_world, x=0.0, y=0.0)
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
    return Tracy.mount_stationary(world, tracy_world, mount_pose)


def test_parsed_description_can_be_given_its_own_root_name():
    root_name = PrefixedName("tracy_mount", "tracy")

    tracy_world = Tracy.parse_description(root_name)

    assert tracy_world.root.name == root_name
    assert tracy_world.get_body_by_name("table") is not tracy_world.root


def test_floor_mounted_tracy_has_its_table_legs_on_the_floor(mounted_tracy):
    table = mounted_tracy.root

    legs_bottom_z = (
        table.collision.as_bounding_box_collection_in_frame(mounted_tracy._world.root)
        .bounding_box()
        .min_z
    )

    assert legs_bottom_z == pytest.approx(0.0, abs=1e-6)
    assert mounted_tracy.table_top_z > 0.5


def test_equipping_gives_every_arm_and_gripper_degree_of_freedom_one_servo(
    mounted_tracy,
):
    actuators = equip_for_mujoco(mounted_tracy)

    driven_degrees_of_freedom = {
        connection.raw_dof.name.name
        for arm in mounted_tracy.get_arms()
        for connection in arm.active_connections + arm.end_effector.active_connections
    }
    assert set(actuators) == driven_degrees_of_freedom
    assert TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE in actuators
    assert len(mounted_tracy._world.actuators) == len(actuators)


def test_equipping_declares_each_joints_own_servo(mounted_tracy):
    equip_for_mujoco(mounted_tracy)

    world = mounted_tracy._world
    shoulder = world.get_connection_by_name(TracyJoint.LEFT_SHOULDER_PAN)
    knuckle = world.get_connection_by_name(TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE)
    expected_gains, expected_dynamics = mounted_tracy.left_arm.servo_for(shoulder)
    assert shoulder.raw_dof.servo_gains == expected_gains
    assert shoulder.dynamics == expected_dynamics
    gripper = mounted_tracy.left_arm.end_effector
    assert (knuckle.raw_dof.servo_gains, knuckle.dynamics) == gripper.servo_for(knuckle)


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


def test_equipping_overwrites_the_descriptions_finger_velocity_limit(mounted_tracy):
    equip_for_mujoco(mounted_tracy)

    gripper = mounted_tracy.left_arm.end_effector
    knuckle = mounted_tracy._world.get_connection_by_name(
        TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE
    )

    assert knuckle.raw_dof.limits.upper.velocity == gripper.finger_velocity_limit
    assert knuckle.raw_dof.limits.lower.velocity == -gripper.finger_velocity_limit


def test_equipping_compensates_gravity_and_lets_the_links_pass_through_each_other(
    mounted_tracy, tmp_path
):
    """
    Every arm and gripper link is gravity-compensated, and the compiled model excludes
    contacts between the robot's own links while the fingers keep colliding with the
    table they may press into.

    Pairs the description itself lists as adjacent, such as the table and the arm bases
    mounted on it, stay excluded.
    """
    equip_for_mujoco(mounted_tracy)

    for arm in mounted_tracy.get_arms():
        for body in arm.bodies + arm.end_effector.bodies:
            assert (
                body.simulator_property(MujocoBody).gravitation_compensation_factor
                == 1.0
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
    equip_for_mujoco(mounted_tracy)
    for arm in mounted_tracy.get_arms():
        arm.get_joint_state_by_type(StaticJointState.PARK).apply_to(world)
    world.notify_state_change()
    tool_frame = mounted_tracy.left_arm.end_effector.tool_frame
    parked = world.compute_forward_kinematics_np(world.root, tool_frame)[:3, 3]

    with RealTimeSimulation(
        world=world, headless=True, real_time_factor=None
    ) as simulation:
        simulation.advance(1.0)
        simulated = simulation.mujoco_mirror.simulator.get_body_position(
            body_name=tool_frame.name.name
        ).result

    assert list(simulated) == pytest.approx(list(parked), abs=0.01)


# %% the gripper's own geometry


def test_gripper_geometry_names_the_pads_and_the_driving_joint(mounted_tracy):
    gripper = mounted_tracy.left_arm.end_effector

    assert gripper.left_fingertip.name.name == "left_robotiq_85_left_finger_tip_link"
    assert gripper.right_fingertip.name.name == "left_robotiq_85_right_finger_tip_link"
    assert gripper.knuckle_joint == TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE
    assert gripper.knuckle_degree_of_freedom.name.name == (
        TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE
    )
    assert (
        mounted_tracy.right_arm.end_effector.knuckle_joint
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
    limits = gripper.knuckle_degree_of_freedom.limits
    open_angle, closed_angle = limits.lower.position, limits.upper.position
    state_before = mounted_tracy._world.state[
        gripper.knuckle_degree_of_freedom.id
    ].position

    narrow = gripper.knuckle_angle_for_half_width(0.02)
    wide = gripper.knuckle_angle_for_half_width(0.03)

    assert gripper.knuckle_angle_for_half_width(1.0) == open_angle
    assert gripper.knuckle_angle_for_half_width(0.0) == closed_angle
    assert open_angle < wide < narrow < closed_angle
    assert (
        mounted_tracy._world.state[gripper.knuckle_degree_of_freedom.id].position
        == state_before
    )

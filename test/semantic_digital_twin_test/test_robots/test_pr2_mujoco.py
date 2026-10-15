"""
Tests for simulating the PR2 physically in MuJoCo: the servos driving its joints and the
drive moving its base across the floor.
"""

from __future__ import annotations

from datetime import timedelta

import mujoco
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from ...pytest_environment import runs_in_continuous_integration

from semantic_digital_twin.adapters.multi_sim import MujocoBuilder, MujocoSim
from semantic_digital_twin.datastructures.definitions import (
    GripperState,
    StaticJointState,
    TorsoState,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.pr2 import PR2, PR2Joint
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.specifications.robots import RobotSpecification
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.world_description.world_entity import (
    Body,
    GravityCompensation,
    PositionServo,
)


def _spawn_pr2(odom_T_robot_start: HomogeneousTransformationMatrix | None) -> PR2:
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
    return RobotSpecification(PR2, odom_T_robot_start=odom_T_robot_start).spawn(world)


@pytest.fixture
def pr2() -> PR2:
    return _spawn_pr2(odom_T_robot_start=None)


def _drive_joints(builder: MujocoBuilder, pr2: PR2) -> list[mujoco.MjsJoint]:
    """
    :return: The joints the compiled model moves the PR2's base with.
    """
    base = next(body for body in builder.spec.bodies if body.name == pr2.root.name.name)
    return list(base.joints)


def _simulated_base_pose(simulation: MujocoSim, pr2: PR2) -> tuple[float, float, float]:
    """
    :return: The x, y and yaw the simulated base stands at.
    """
    simulator = simulation.simulator
    x, y, _ = simulator.get_body_position(body_name=pr2.root.name.name).result
    w, i, j, k = simulator.get_body_quaternion(body_name=pr2.root.name.name).result
    yaw = Rotation.from_quat([i, j, k, w]).as_euler("xyz")[2]
    return float(x), float(y), float(yaw)


# %% the servos the PR2 declares


def test_every_commanded_joint_the_fingers_and_the_drive_are_driven_by_one_servo(pr2):
    """
    Each joint a controller commands, the finger joint of each gripper and the drive's
    x, y and yaw are driven by exactly one position servo.
    """
    world = pr2._world
    drive = pr2.drive
    commanded = {
        connection.raw_dof
        for connection in world.get_connections_of_branch(pr2.root)
        if isinstance(connection, ActiveConnection1DOF)
        and connection.has_hardware_interface
    }
    fingers = {
        arm.end_effector.thumb.root.parent_connection.raw_dof for arm in pr2.all_arms
    }

    driven = [
        degree_of_freedom
        for actuator in world.actuators
        for degree_of_freedom in actuator.dofs
    ]

    assert all(isinstance(actuator, PositionServo) for actuator in world.actuators)
    expected = commanded | fingers | {drive.x, drive.y, drive.yaw}
    assert sorted(str(dof.name) for dof in driven) == sorted(
        str(dof.name) for dof in expected
    )


def test_the_drive_servos_have_the_gains_the_base_declares(pr2):
    world = pr2._world
    drive = pr2.drive
    drive_servos = pr2.mobile_base.drive_servos

    gains_by_degree_of_freedom = {
        degree_of_freedom: actuator.gains
        for actuator in world.actuators
        for degree_of_freedom in actuator.dofs
    }

    assert gains_by_degree_of_freedom[drive.x] == drive_servos.translation_gains
    assert gains_by_degree_of_freedom[drive.y] == drive_servos.translation_gains
    assert gains_by_degree_of_freedom[drive.yaw] == drive_servos.rotation_gains


def test_every_body_standing_on_the_base_carries_its_own_weight(pr2):
    for body in pr2.mobile_base.bodies:
        assert body.get_simulator_property_of_type(GravityCompensation) == (
            GravityCompensation(fraction=1.0)
        )


# %% the compiled model


def test_the_compiled_model_moves_the_base_along_x_and_y_and_about_z(pr2, tmp_path):
    builder = MujocoBuilder()
    builder.build_world(world=pr2._world, file_path=str(tmp_path / "scene.xml"))

    drive_joints = _drive_joints(builder, pr2)

    assert [(joint.type, list(joint.axis)) for joint in drive_joints] == [
        (mujoco.mjtJoint.mjJNT_SLIDE, [1.0, 0.0, 0.0]),
        (mujoco.mjtJoint.mjJNT_SLIDE, [0.0, 1.0, 0.0]),
        (mujoco.mjtJoint.mjJNT_HINGE, [0.0, 0.0, 1.0]),
    ]
    actuated_joints = {actuator.target for actuator in builder.spec.actuators}
    assert {joint.name for joint in drive_joints} <= actuated_joints


def test_the_drive_joints_are_named_after_the_robot_and_the_axis_they_move(
    pr2, tmp_path
):
    builder = MujocoBuilder()
    builder.build_world(world=pr2._world, file_path=str(tmp_path / "scene.xml"))

    assert [joint.name for joint in _drive_joints(builder, pr2)] == [
        "pr2_omni_drive_x",
        "pr2_omni_drive_y",
        "pr2_omni_drive_yaw",
    ]


def test_a_drive_without_servos_keeps_the_base_where_it_is_built(pr2, tmp_path):
    """
    A robot whose base is moved kinematically keeps it bolted to its ``odom`` in the
    compiled model.
    """
    world = pr2._world
    drive = pr2.drive
    with world.modify_world():
        for actuator in list(world.actuators):
            if set(actuator.dofs) & {drive.x, drive.y, drive.yaw}:
                world.remove_actuator(actuator)
    builder = MujocoBuilder()
    builder.build_world(world=world, file_path=str(tmp_path / "scene.xml"))

    assert _drive_joints(builder, pr2) == []


# %% the physics


@pytest.mark.skipif(
    not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
)
def test_the_servos_hold_the_parked_arms_and_the_raised_torso_up(pr2):
    """
    A joint with no servo would be written straight into MuJoCo and sag under its own
    weight between one control cycle and the next.
    """
    world = pr2._world
    for arm in pr2.all_arms:
        arm.get_joint_state_by_type(StaticJointState.PARK).apply_to(world)
    pr2.torso.get_joint_state_by_type(TorsoState.HIGH).apply_to(world)
    world.notify_state_change()
    tool_frames = [arm.end_effector.tool_frame for arm in pr2.all_arms]
    parked = [
        world.compute_forward_kinematics_np(world.root, tool_frame)[:3, 3]
        for tool_frame in tool_frames
    ]

    simulation = MujocoSim(world=world, headless=True)
    simulation.start_stepped_simulation()
    try:
        simulation.step_simulation(timedelta(seconds=1))
        simulated = [
            simulation.simulator.get_body_position(
                body_name=tool_frame.name.name
            ).result
            for tool_frame in tool_frames
        ]
    finally:
        simulation.stop_simulation()

    for simulated_position, parked_position in zip(simulated, parked):
        assert list(simulated_position) == pytest.approx(
            list(parked_position), abs=0.01
        )


@pytest.mark.skipif(
    not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
)
def test_the_servos_drive_the_joints_to_a_commanded_configuration(pr2):
    world = pr2._world
    commanded = {
        PR2Joint.TORSO_LIFT: 0.2,
        PR2Joint.HEAD_PAN: 0.5,
        PR2Joint.HEAD_TILT: 0.3,
        PR2Joint.RIGHT_SHOULDER_PAN: -0.5,
        PR2Joint.RIGHT_SHOULDER_LIFT: 0.3,
        PR2Joint.RIGHT_UPPER_ARM_ROLL: -0.4,
        PR2Joint.RIGHT_ELBOW_FLEX: -1.0,
        PR2Joint.RIGHT_FOREARM_ROLL: 0.5,
        PR2Joint.RIGHT_WRIST_FLEX: -0.6,
        PR2Joint.RIGHT_WRIST_ROLL: 0.7,
    }

    simulation = MujocoSim(world=world, headless=True)
    simulation.start_stepped_simulation()
    try:
        for joint_name, position in commanded.items():
            connection = world.get_connection_by_name(joint_name)
            world.state[connection.raw_dof.id].position = position
        world.notify_state_change()
        simulation.step_simulation(timedelta(seconds=3))
        reached = {
            joint_name: simulation.simulator.get_joint_value(joint_name).result
            for joint_name in commanded
        }
    finally:
        simulation.stop_simulation()

    assert reached == pytest.approx(commanded, abs=0.02)


@pytest.mark.skipif(
    not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
)
def test_the_finger_servo_closes_the_gripper(pr2):
    world = pr2._world
    gripper = pr2.right_arm.end_effector
    gripper.get_joint_state_by_type(GripperState.OPEN).apply_to(world)
    world.notify_state_change()
    finger_joint = gripper.thumb.root.parent_connection
    closed = gripper.get_joint_state_by_type(GripperState.CLOSE)

    simulation = MujocoSim(world=world, headless=True)
    simulation.start_stepped_simulation()
    try:
        closed.apply_to(world)
        world.notify_state_change()
        simulation.step_simulation(timedelta(seconds=1))
        reached = simulation.simulator.get_joint_value(finger_joint.name.name).result
    finally:
        simulation.stop_simulation()

    assert reached == pytest.approx(
        world.state[finger_joint.raw_dof.id].position, abs=0.02
    )


@pytest.mark.skipif(
    not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
)
def test_the_drive_moves_the_base_to_the_commanded_pose(pr2):
    world = pr2._world
    drive = pr2.drive
    commanded = (0.5, -0.3, 0.4)

    simulation = MujocoSim(world=world, headless=True)
    simulation.start_stepped_simulation()
    try:
        for degree_of_freedom, position in zip(
            (drive.x, drive.y, drive.yaw), commanded
        ):
            world.state[degree_of_freedom.id].position = position
        world.notify_state_change()
        simulation.step_simulation(timedelta(seconds=3))
        reached = _simulated_base_pose(simulation, pr2)
    finally:
        simulation.stop_simulation()

    assert reached == pytest.approx(commanded, abs=0.02)


@pytest.mark.skipif(
    not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
)
def test_the_base_starts_where_the_world_has_it():
    start = HomogeneousTransformationMatrix.from_xyz_rpy(x=1.0, y=2.0, yaw=0.5)
    pr2 = _spawn_pr2(odom_T_robot_start=start)

    simulation = MujocoSim(world=pr2._world, headless=True)
    simulation.start_stepped_simulation()
    try:
        simulation.step_simulation(timedelta(seconds=1))
        reached = _simulated_base_pose(simulation, pr2)
    finally:
        simulation.stop_simulation()

    assert reached == pytest.approx((1.0, 2.0, 0.5), abs=0.02)

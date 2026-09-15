"""
Tests for mounting Tracy into a world and equipping it for physical simulation in
MuJoCo; skipped where Tracy's description is not installed.
"""

from __future__ import annotations

import os

import pytest

from semantic_digital_twin.adapters.multi_sim import MujocoBody, MujocoGeom
from semantic_digital_twin.adapters.mujoco_tuning import CollisionGroup
from semantic_digital_twin.adapters.real_time_simulation import RealTimeSimulation
from semantic_digital_twin.datastructures.definitions import StaticJointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy, TracyJoint, TracyServoTuning
from semantic_digital_twin.utils import tracy_installed
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

pytestmark = pytest.mark.skipif(
    not tracy_installed(), reason="iai_tracy_description is not installed"
)

only_run_in_ci = os.environ.get("CI", "false").lower() == "false"


@pytest.fixture
def mounted_tracy() -> Tracy:
    tracy_world = Tracy.parse_description()
    mount_position, _ = Tracy.floor_mount_position(tracy_world, x=0.0, y=0.0)
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
    return Tracy.mount_stationary(world, tracy_world, mount_position)


def test_parsed_description_carries_no_actuator():
    tracy_world = Tracy.parse_description()

    assert tracy_world.actuators == []
    assert tracy_world.root.name == PrefixedName("tracy_mount", "tracy")


def test_floor_mounted_tracy_has_its_table_legs_on_the_floor(mounted_tracy):
    tracy_world = Tracy.parse_description()
    _, expected_table_top_z = Tracy.floor_mount_position(tracy_world, x=0.0, y=0.0)
    table = mounted_tracy.root

    legs_bottom_z = (
        table.collision.as_bounding_box_collection_in_frame(mounted_tracy._world.root)
        .bounding_box()
        .min_z
    )

    assert legs_bottom_z == pytest.approx(0.0, abs=1e-6)
    assert mounted_tracy.table_top_z == pytest.approx(expected_table_top_z)


def test_equipping_gives_every_arm_and_gripper_degree_of_freedom_one_servo(
    mounted_tracy,
):
    actuators = mounted_tracy.equip_for_mujoco()

    driven_degrees_of_freedom = {
        connection.raw_dof.name.name
        for arm in mounted_tracy.get_arms()
        for connection in arm.active_connections + arm.end_effector.active_connections
    }
    assert set(actuators) == driven_degrees_of_freedom
    assert TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE in actuators
    assert len(mounted_tracy._world.actuators) == len(actuators)


def test_equipping_raises_the_gripper_velocity_limit_to_the_tunings(mounted_tracy):
    tuning = TracyServoTuning(gripper_joint_velocity_limit=0.5)

    mounted_tracy.equip_for_mujoco(tuning)

    knuckle = mounted_tracy._world.get_connection_by_name(
        TracyJoint.LEFT_GRIPPER_LEFT_KNUCKLE
    )
    assert knuckle.raw_dof.limits.upper.velocity == 0.5
    assert knuckle.raw_dof.limits.lower.velocity == -0.5


def test_equipping_compensates_gravity_and_excludes_self_collision(mounted_tracy):
    mounted_tracy.equip_for_mujoco()

    for arm in mounted_tracy.get_arms():
        for body in arm.bodies + arm.end_effector.bodies:
            assert (
                body.simulator_property(MujocoBody).gravitation_compensation_factor
                == 1.0
            )
    for body in mounted_tracy.bodies_with_collision:
        if body is mounted_tracy.root:
            continue
        for shape in body.collision:
            mujoco_geom = shape.simulator_property(MujocoGeom)
            assert mujoco_geom.contype == CollisionGroup.ROBOT
            assert mujoco_geom.conaffinity == CollisionGroup.EXTERNAL
    for shape in mounted_tracy.root.collision:
        assert shape.simulator_property(MujocoGeom) is None


@pytest.mark.skipif(only_run_in_ci, reason="MuJoCo tests only run in CI")
def test_the_servos_hold_the_parked_arms_up(mounted_tracy):
    """
    A joint with no servo would be written straight into MuJoCo and sag under its own
    weight between one control cycle and the next.
    """
    world = mounted_tracy._world
    mounted_tracy.equip_for_mujoco()
    for arm in mounted_tracy.get_arms():
        arm.get_joint_state_by_type(StaticJointState.PARK).apply_to(world)
    world.notify_state_change()
    tool_frame = mounted_tracy.left_arm.end_effector.tool_frame
    parked = world.compute_forward_kinematics_np(world.root, tool_frame)[:3, 3]

    with RealTimeSimulation(
        world=world, headless=True, real_time_factor=None
    ) as simulation:
        simulation.advance(1.0)
        simulated = simulation.mirror.simulator.get_body_position(
            body_name=tool_frame.name.name
        ).result

    assert list(simulated) == pytest.approx(list(parked), abs=0.01)

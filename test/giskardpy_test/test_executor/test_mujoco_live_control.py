"""
Giskard's own control loop driving a physically simulated Tracy live: each control
cycle's command becomes the servos' set point through the world state, and the physics
steps in lockstep between cycles.

Skipped where Tracy's description is not installed.
"""

from __future__ import annotations

import numpy
import pytest

from ...pytest_environment import runs_in_continuous_integration

from giskardpy.executor import Executor
from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.graph_node import EndMotion
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from giskardpy.motion_statechart.tasks.cartesian_tasks import CartesianPosition
from giskardpy.qp.qp_controller_config import QPControllerConfig
from semantic_digital_twin.adapters.mujoco_tuning import equip_for_mujoco
from semantic_digital_twin.adapters.real_time_simulation import RealTimeSimulation
from semantic_digital_twin.datastructures.definitions import StaticJointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.utils import tracy_installed
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

pytestmark = [
    pytest.mark.skipif(
        not tracy_installed(), reason="iai_tracy_description is not installed"
    ),
    pytest.mark.skipif(
        not runs_in_continuous_integration(), reason="MuJoCo tests only run in CI"
    ),
]


@pytest.fixture
def parked_tracy() -> Tracy:
    tracy_world = Tracy.parse_description()
    mount_pose = Tracy.floor_mount_pose(tracy_world, x=0.0, y=0.0)
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(Body(name=PrefixedName("floor")))
    robot = Tracy.mount_stationary(world, tracy_world, mount_pose)
    equip_for_mujoco(robot)
    for arm in robot.get_arms():
        arm.get_joint_state_by_type(StaticJointState.PARK).apply_to(world)
    world.notify_state_change()
    return robot


def test_the_simulated_arm_reaches_the_pose_giskard_commands_live(parked_tracy):
    """
    A goal ticked by Giskard against the world is reached by the arm in the physics, not
    merely in the world's own belief: every cycle's command is handed to the servos as
    their set point and the physics steps in between.
    """
    control_frequency = 50
    time_limit = 10.0
    tracking_tolerance = 0.02
    world = parked_tracy._world
    tool_frame = parked_tracy.left_arm.end_effector.tool_frame
    start = world.compute_forward_kinematics_np(world.root, tool_frame)[:3, 3]
    goal_point = Point3(start[0], start[1], start[2] + 0.15, reference_frame=world.root)
    reach = CartesianPosition(
        name="reach", root_link=world.root, tip_link=tool_frame, goal_point=goal_point
    )
    motion_statechart = MotionStatechart()
    motion_statechart.add_nodes([reach, EndMotion.when_true(reach)])
    controller_config = QPControllerConfig(target_frequency=control_frequency)
    executor = Executor(
        context=MotionStatechartContext(
            world=world, qp_controller_config=controller_config
        )
    )
    executor.compile(motion_statechart=motion_statechart)

    with RealTimeSimulation(
        world=world, headless=True, real_time_factor=None
    ) as simulation:
        for _ in range(round(time_limit * control_frequency)):
            if motion_statechart.is_end_motion():
                break
            executor.tick()
            simulation.advance(controller_config.control_dt)
        simulation.advance(1.0)
        simulated = numpy.array(
            simulation.mujoco_mirror.simulator.get_body_position(
                body_name=tool_frame.name.name
            ).result
        )

    assert motion_statechart.is_end_motion()
    assert numpy.linalg.norm(simulated - goal_point.to_np()[:3]) <= tracking_tolerance

"""
Tests for :mod:`experiments.tracy_experiments.real_time_simulation`: a follower world's
joints take the simulated positions after every advance, observers are told how far the
simulation has come, and an unpaced simulation does not wait for the wall clock.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import pytest
from typing_extensions import List

from experiments.tracy_experiments.equipment import (
    equip_arms_with_servos,
    joint_state_of_type,
    parse_tracy,
    tracy_table_mount_position,
)
from experiments.montessori.world import mount_stationary_robot
from experiments.tracy_experiments.real_time_simulation import (
    RealTimeSimulation,
    SimulationObserver,
)
from semantic_digital_twin.datastructures.definitions import StaticJointState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

ADVANCE = 0.2
"""
Simulated seconds each test advances by.
"""


@dataclass
class _ObserverKeepingTheTimes(SimulationObserver):
    """
    Keeps every simulated time it was told.
    """

    told: List[float] = field(default_factory=list)

    def simulation_advanced(self, simulated_time: float) -> None:
        self.told.append(simulated_time)


def _mounted_tracy() -> tuple[World, Tracy]:
    """
    :return: A world with Tracy bolted to its root, and the robot.
    """
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(
            Body(name=PrefixedName(name="root", prefix="world"))
        )
    tracy = parse_tracy()
    mount_position, _ = tracy_table_mount_position(tracy, x=0.0, y=0.0)
    robot = mount_stationary_robot(world, Tracy, tracy, mount_position)
    return world, robot


def _first_arm_joint_name(robot: Tracy) -> PrefixedName:
    """
    :return: The name of the left arm's first joint.
    """
    return robot.left_arm.active_connections[0].raw_dof.name


def _position(world: World, name: PrefixedName) -> float:
    """
    :return: A joint's position in a world, by name.
    """
    return world.state[world.get_degree_of_freedom_by_name(name).id].position


def test_a_followers_joints_take_the_simulated_positions_after_an_advance():
    reality, robot = _mounted_tracy()
    actuators = equip_arms_with_servos(reality, robot)
    joint_state_of_type(robot.left_arm, StaticJointState.PARK).apply_to(reality)
    reality.notify_state_change()
    belief = parse_tracy()
    joint = _first_arm_joint_name(robot)
    assert _position(belief, joint) != _position(reality, joint)

    with RealTimeSimulation(
        world=reality, headless=True, paced_to_the_wall_clock=False, followers=[belief]
    ) as simulation:
        parked = joint_state_of_type(robot.left_arm, StaticJointState.PARK)
        for connection, target in zip(parked.connections, parked.target_values):
            simulation.command(actuators[connection.raw_dof.name.name], target)
        simulation.advance(ADVANCE)

    for connection in robot.left_arm.active_connections:
        name = connection.raw_dof.name
        assert _position(belief, name) == _position(reality, name)


def test_an_observer_is_told_the_simulated_time_after_every_advance():
    reality, _ = _mounted_tracy()
    observer = _ObserverKeepingTheTimes()

    with RealTimeSimulation(
        world=reality,
        headless=True,
        paced_to_the_wall_clock=False,
        observers=[observer],
    ) as simulation:
        simulation.advance(ADVANCE)
        simulation.advance(ADVANCE)

    assert observer.told == pytest.approx([ADVANCE, 2 * ADVANCE])


def test_an_unpaced_simulation_does_not_wait_for_the_wall_clock():
    reality, _ = _mounted_tracy()

    with RealTimeSimulation(
        world=reality, headless=True, paced_to_the_wall_clock=False
    ) as simulation:
        started = time.monotonic()
        simulation.advance(1.0)
        elapsed = time.monotonic() - started

    assert elapsed < 1.0

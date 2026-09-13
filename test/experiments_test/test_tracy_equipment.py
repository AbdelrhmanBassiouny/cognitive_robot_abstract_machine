"""
How Tracy is fitted out for a simulation: the links its servos drive are held up against
gravity where the servos are what moves it, and every link below its root where nothing
drives it.
"""

from __future__ import annotations

from semantic_digital_twin.adapters.multi_sim import MujocoBody
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from experiments.tracy_experiments.equipment import (
    apply_gravity_compensation,
    compensate_gravity_on_every_link,
    parse_tracy,
)

A_FRAME_STATING_NO_MASS = "left_flange"
"""
One of the frames Tracy's description hangs off a wrist as a body of its own, without
stating a mass for it.
"""


def compensated_bodies_of(world: World) -> set[Body]:
    """
    Every body the world holds that is given full gravity compensation.

    :param world: The world to read.
    """
    return {
        body
        for body in world.bodies
        if any(
            isinstance(stated, MujocoBody)
            and stated.gravitation_compensation_factor == 1.0
            for stated in body.simulator_additional_properties
        )
    }


def test_gravity_compensation_covers_the_links_of_the_arms_and_their_grippers():
    world = parse_tracy()
    robot = Tracy.from_world(world)

    apply_gravity_compensation(world, robot)

    arms_and_grippers = {
        body
        for arm in robot.get_arms()
        for body in arm.bodies + arm.end_effector.bodies
    }
    compensated = compensated_bodies_of(world)
    assert compensated == arms_and_grippers
    assert world.get_body_by_name(A_FRAME_STATING_NO_MASS) not in compensated


def test_compensating_every_link_covers_every_link_below_the_robots_root():
    world = parse_tracy()
    robot = Tracy.from_world(world)

    compensate_gravity_on_every_link(world, robot)

    below_the_root = {
        entity
        for entity in world.get_kinematic_structure_entities_of_branch(robot.root)
        if isinstance(entity, Body) and entity is not robot.root
    }
    compensated = compensated_bodies_of(world)
    assert compensated == below_the_root
    assert world.get_body_by_name(A_FRAME_STATING_NO_MASS) in compensated
    assert robot.root not in compensated

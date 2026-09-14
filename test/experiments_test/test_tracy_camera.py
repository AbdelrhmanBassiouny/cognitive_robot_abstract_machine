"""
The camera Tracy's description carries, as a simulated picture is taken through it.
"""

from __future__ import annotations

from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.world import World

from experiments.tracy_experiments.camera import (
    CAMERA_LINK_NAME,
    camera_of_the_robot,
    camera_on_tracy,
    tracys_camera,
)
from experiments.tracy_experiments.equipment import parse_tracy


def test_tracys_camera_stands_on_its_camera_link_and_is_not_hung_yet():
    world = parse_tracy()
    Tracy.from_world(world)

    camera = tracys_camera(world)

    assert camera.body is world.get_body_by_name(CAMERA_LINK_NAME)
    assert camera not in camera.body.simulator_additional_properties


def test_the_camera_hung_on_tracy_is_the_one_its_description_carries():
    world = parse_tracy()
    Tracy.from_world(world)

    hung = camera_on_tracy(world)

    assert (
        hung in world.get_body_by_name(CAMERA_LINK_NAME).simulator_additional_properties
    )
    assert hung == tracys_camera(world)


def test_the_robots_camera_is_tracys_where_the_world_holds_tracy():
    world = parse_tracy()
    Tracy.from_world(world)

    assert camera_of_the_robot(world) == tracys_camera(world)


def test_a_world_holding_no_robot_has_no_camera_of_its_own():
    assert camera_of_the_robot(World()) is None

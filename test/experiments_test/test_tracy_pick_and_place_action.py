from coraplex.datastructures.enums import Arms
from experiments.montessori.world import mount_stationary_robot
from experiments.tracy_experiments.equipment import (
    parse_tracy,
    tracy_table_mount_position,
)
from experiments.tracy_experiments.pick_and_place_action import (
    _bounding_box_center_world,
    _finger_midpoint_offset,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body


def _mounted_tracy() -> tuple[World, Tracy]:
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(
            Body(name=PrefixedName(name="root", prefix="world"))
        )
    tracy_world = parse_tracy()
    mount_position, _ = tracy_table_mount_position(tracy_world, x=0.0, y=0.0)
    robot = mount_stationary_robot(world, Tracy, tracy_world, mount_position)
    return world, robot


def test_bounding_box_center_world_is_the_average_of_the_bodys_own_min_and_max():
    world, robot = _mounted_tracy()
    body = world.get_body_by_name("left_robotiq_85_left_finger_tip_link")

    center = _bounding_box_center_world(world, body)

    bounding_box = body.collision[0].local_frame_bounding_box
    root_transform_body = world.compute_forward_kinematics_np(world.root, body)
    expected_local_center = [
        (bounding_box.min_x + bounding_box.max_x) / 2,
        (bounding_box.min_y + bounding_box.max_y) / 2,
        (bounding_box.min_z + bounding_box.max_z) / 2,
    ]
    expected = (
        root_transform_body[:3, :3] @ expected_local_center + root_transform_body[:3, 3]
    )
    assert list(center) == list(expected)


def test_finger_midpoint_offset_differs_between_left_and_right_arm():
    world, robot = _mounted_tracy()

    left_offset = _finger_midpoint_offset(robot, Arms.LEFT)
    right_offset = _finger_midpoint_offset(robot, Arms.RIGHT)

    assert list(left_offset) != list(right_offset)

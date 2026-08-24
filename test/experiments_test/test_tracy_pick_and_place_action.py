from coraplex.datastructures.enums import Arms
from experiments.montessori.world import mount_stationary_robot
from experiments.tracy_experiments.equipment import (
    parse_tracy,
    tracy_table_mount_position,
)
from experiments.tracy_experiments.pick_and_place_action import (
    _bounding_box_center_world,
    _finger_midpoint_offset,
    _grasp_target_z,
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


def test_grasp_target_z_clears_the_bodys_own_resting_surface():
    world, robot = _mounted_tracy()
    body = world.get_body_by_name("table")
    pad = world.get_body_by_name("left_robotiq_85_left_finger_tip_link")

    grasp_z = _grasp_target_z(world, robot, Arms.LEFT, body, table_clearance=0.0)

    bounding_box = body.collision[0].local_frame_bounding_box
    body_center_z = _bounding_box_center_world(world, body)[2]
    body_bottom_z = body_center_z - (bounding_box.max_z - bounding_box.min_z) / 2
    pad_bounding_box = pad.collision[0].local_frame_bounding_box
    pad_half_height = (pad_bounding_box.max_z - pad_bounding_box.min_z) / 2
    assert grasp_z == body_bottom_z + pad_half_height


def test_finger_midpoint_offset_differs_between_left_and_right_arm():
    world, robot = _mounted_tracy()

    left_offset = _finger_midpoint_offset(robot, Arms.LEFT)
    right_offset = _finger_midpoint_offset(robot, Arms.RIGHT)

    assert list(left_offset) != list(right_offset)

import numpy

from coraplex.datastructures.enums import Arms
from experiments.montessori.world import mount_stationary_robot
from experiments.tracy_experiments.equipment import (
    parse_tracy,
    tracy_table_mount_position,
)
from coraplex.datastructures.enums import ApproachDirection, VerticalAlignment
from coraplex.datastructures.grasp import GraspDescription
from coraplex.robot_plans.mixins import ManipulatesBodies
from coraplex.view_manager import ViewManager
from coraplex.robot_plans.actions.core.insertion import InsertionAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from experiments.tracy_experiments.pick_and_place_action import (
    InsertionActionMujoco,
    PickUpActionMujoco,
    PlaceActionMujoco,
    _bounding_box_center_world,
    _finger_midpoint_offset,
    _grasp_pose_builder,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose
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


# %% what the actions say they act on


def test_both_actions_act_on_the_body_they_are_given():
    """
    A plan chart reads which body an item of the plan acted on off the action itself,
    which is what lets it tell the robot's own pick-up from someone else's shove.
    """
    world, robot = _mounted_tracy()
    piece = world.get_body_by_name("left_robotiq_85_left_finger_tip_link")
    grasp = GraspDescription(
        ApproachDirection.FRONT,
        VerticalAlignment.TOP,
        ViewManager.get_end_effector_view(Arms.LEFT, robot),
    )
    pick = PickUpActionMujoco(
        object_designator=piece,
        arm=Arms.LEFT,
        grasp_description=grasp,
        sim=None,
        actuators={},
    )
    place = PlaceActionMujoco(
        object_designator=piece,
        target_location=Pose(),
        arm=Arms.LEFT,
        grasp_description=grasp,
        sim=None,
        actuators={},
    )

    assert isinstance(pick, ManipulatesBodies) and isinstance(place, ManipulatesBodies)
    assert pick.manipulated_bodies == [piece]
    assert place.manipulated_bodies == [piece]


# %% how the gripper is turned to reach


def test_the_gripper_is_turned_the_way_the_grasp_says():
    """
    What the gripper is held in is the grasp's own orientation, so the side of the body
    a grasp names is the side the hand actually comes at it from.
    """
    world, robot = _mounted_tracy()
    grasp = GraspDescription(
        ApproachDirection.LEFT,
        VerticalAlignment.TOP,
        ViewManager.get_end_effector_view(Arms.LEFT, robot),
    )

    reached_for = _grasp_pose_builder(world, robot, Arms.LEFT, grasp)(1.0, 0.2, 0.9)

    assert numpy.allclose(
        reached_for.to_quaternion().to_np(), grasp.grasp_orientation().to_np()
    )


# %% which action of a plan each of these carries out


def test_each_action_says_which_action_of_a_plan_it_carries_out():
    assert [
        action.action_it_carries_out()
        for action in (PickUpActionMujoco, PlaceActionMujoco, InsertionActionMujoco)
    ] == [PickUpAction, PlaceAction, InsertionAction]

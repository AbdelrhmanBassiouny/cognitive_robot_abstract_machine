"""
Pouring demo: a robot pours from a cup held in its right gripper into a bowl on the
apartment kitchen counter.
"""

from typing_extensions import List, Type

from experiments.tool_based_actions.simple_demo.demo_world import (
    BOWL_COLOR,
    CUP_COLOR,
    POUR_MOUNT,
    TARGET_POSITION_XYZ,
    parse_object,
    standing_pose_at,
)
from semantic_digital_twin.datastructures.definitions import GripperState, TorsoState
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Bowl,
    PouringCup,
)
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world_description.world_entity import Body

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms
from coraplex.execution_environment import simulated_robot, simulated_robot_advanced
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.actions.composite.tool_based import PouringAction
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import (
    MoveTorsoAction,
    ParkArmsAction,
    SetGripperAction,
)
from coraplex.testing import attach_tool, setup_world, start_visualization

# %% plan composition


def pouring_actions(
    robot: AbstractRobot,
    target_container: Body,
    source_container: PouringCup,
    base_pose: Pose,
) -> List[ActionDescription]:
    """
    Build the action sequence that pours from the cup into the target container.

    The torso is only raised on robots whose torso defines the high state; robots
    without a liftable torso pour from wherever their arms already are.

    :param robot: Robot performing the pour.
    :param target_container: Body that is poured into.
    :param source_container: Cup that is poured from.
    :param base_pose: Pose the robot navigates to before pouring.
    """
    actions: List[ActionDescription] = [
        SetGripperAction(Arms.RIGHT, GripperState.CLOSE),
        ParkArmsAction(Arms.BOTH),
    ]
    torso = robot.get_torso_if_specified()
    if torso is not None and torso.has_joint_state_of_type(TorsoState.HIGH):
        actions.append(MoveTorsoAction(TorsoState.HIGH))
    actions.append(NavigateAction(base_pose))
    actions.append(
        PouringAction(
            target_container=target_container,
            source_container=source_container,
            arm=Arms.RIGHT,
        )
    )
    return actions


# %% demo entry point


def main(robot_type: Type[AbstractRobot] = PR2) -> None:
    """
    Build the demo world and run the plan on the simulated robot.

    :param robot_type: Robot performing the pour.
    """
    world = setup_world(robot_type)

    bowl_world = parse_object("bowl.stl", color=BOWL_COLOR)
    with world.modify_world():
        world.merge_world_at_pose(
            bowl_world,
            HomogeneousTransformationMatrix.from_xyz_quaternion(
                *TARGET_POSITION_XYZ, reference_frame=world.root
            ),
        )
    start_visualization(world)
    robot = robot_type.from_world(world)
    context = Context(world=world, robot=robot, _debug=False, ros_node=None)

    cup_body = attach_tool(
        world,
        robot,
        Arms.RIGHT,
        parse_object("jeroen_cup.stl", color=CUP_COLOR),
        POUR_MOUNT,
    )
    bowl_body = world.get_body_by_name("bowl.stl")

    cup = PouringCup(root=cup_body)
    with world.modify_world():
        world.add_semantic_annotations([Bowl(root=bowl_body), cup])

    context.evaluate_conditions = False

    plan = sequential(
        pouring_actions(robot, bowl_body, cup, standing_pose_at(world, robot)),
        context=context,
    ).plan

    with simulated_robot_advanced:
        plan.perform()


if __name__ == "__main__":
    main()

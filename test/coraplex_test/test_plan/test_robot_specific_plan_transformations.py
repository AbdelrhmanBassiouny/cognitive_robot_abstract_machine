from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest
from typing_extensions import List

from coraplex.exceptions import ActionNotExpanded
from coraplex.plans.executors import PlanExecutor
from coraplex.plans.plan_transformation import PlanRewriting, PlanTransformation
from coraplex.plans.underspecified import UnderspecifiedNode
from coraplex.robot_plans.actions.core.container import CloseAction
from coraplex.robot_plans.actions.core.navigation import (
    DrivesBase,
    NavigateAction,
    PathPlanningNavigateAction,
)
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from coraplex.robot_plans.robot_specific_plan_transformations import (
    DriveSimulatedTiagoWithItsDifferentialDrive,
    DriveStretchWithItsDifferentialDrive,
    KeepStretchInFrontOfTheContainerItCloses,
)
from cramph.composites import Parallel, Sequence
from cramph.context import ContextExtension
from cramph.exceptions import StatechartAlreadyCompiledError
from cramph.node import StatechartNode
from giskardpy.motion_statechart.goals.cartesian_goals import DifferentialDriveBaseGoal
from giskardpy.motion_statechart.goals.open_close import Close
from giskardpy.motion_statechart.graph_node import ConvergingTask
from giskardpy.motion_statechart.monitors.overwrite_state_monitors import SetOdometry
from giskardpy.motion_statechart.tasks.align_planes import AlignPlanes
from giskardpy.motion_statechart.tasks.cartesian_tasks import CartesianPose
from giskardpy.motion_statechart.tasks.joint_tasks import JointPositionList
from krrood.entity_query_language.factories import a, variable_from
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.robots.tiago import Tiago
from semantic_digital_twin.semantic_annotations.semantic_annotations import Handle
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World

from ...plan_running import (
    expand,
    robot_executor,
    robot_extensions,
    simulated_executor,
    statechart_of,
)

# %% preparing a plan for a robot


@pytest.fixture
def tiago_context(_tiago_world_setup):
    """
    A world holding a Tiago, the robot and the context extensions of its plans.
    """
    world = deepcopy(_tiago_world_setup)
    robot = world.get_semantic_annotations_by_type(Tiago)[0]
    return world, robot, robot_extensions(robot)


def prepared(
    plan: StatechartNode,
    executor: PlanExecutor,
) -> StatechartNode:
    """
    Expand and rewrite `plan` the way `executor` would before running it.

    :return: The plan, rewritten.
    """
    executor.prepare(statechart_of(executor, plan))
    return plan


def rewriting_with(
    extensions: List[ContextExtension], *transformations: PlanTransformation
) -> List[ContextExtension]:
    """
    :return: `extensions` and a rewriting by `transformations`.
    """
    return [*extensions, PlanRewriting(transformations=list(transformations))]


def every_base_transformation() -> List[PlanTransformation]:
    """
    :return: The transformations that change how a robot drives its base.
    """
    return [
        DriveStretchWithItsDifferentialDrive(),
        DriveSimulatedTiagoWithItsDifferentialDrive(),
    ]


def navigation_to(world: World, **parameters) -> NavigateAction:
    """
    :return: A drive to a pose two meters from the origin of `world`.
    """
    return NavigateAction(
        Pose.from_xyz_rpy(2.0, 2.0, 0.0, reference_frame=world.root), **parameters
    )


def assert_drives_differentially_to(
    goal: StatechartNode, action: NavigateAction, robot: AbstractRobot
) -> None:
    """
    Check that `goal` drives the differential drive of `robot` to where `action` puts
    the base, within the threshold of `action`.
    """
    assert type(goal) is DifferentialDriveBaseGoal
    assert goal.diff_drive_connection is robot.drive
    assert goal.threshold == action.base_pose_threshold
    np.testing.assert_allclose(
        goal.goal_pose.to_np(),
        robot.mobile_base.pose_facing(action.target_location).to_np(),
    )
    assert goal.goal_pose.reference_frame is action.target_location.reference_frame


# %% replacing the body of an action


def test_an_expanded_action_runs_the_body_it_is_given_instead(pr2_apartment_context):
    world, robot, extensions = pr2_apartment_context
    action = expand(MoveTorsoAction(TorsoState.HIGH), extensions)
    former_nodes = [action.action_body, *action.action_body.descendants]
    goal = JointPositionList(
        goal_state=robot.get_torso().get_joint_state_by_type(TorsoState.LOW)
    )

    action.replace_action_body(goal)

    assert action.action_body is goal
    assert action.children == [goal]
    assert goal in action.statechart.nodes
    assert not set(former_nodes) & set(action.statechart.nodes)


def test_an_expanded_action_runs_a_body_deciding_its_own_success_instead(
    pr2_apartment_context,
):
    world, robot, extensions = pr2_apartment_context
    action = expand(MoveTorsoAction(TorsoState.HIGH), extensions)
    body = Sequence(
        [
            JointPositionList(
                goal_state=robot.get_torso().get_joint_state_by_type(TorsoState.LOW)
            )
        ]
    )

    action.replace_action_body(body)

    assert action.action_body is body


def test_an_action_that_was_not_expanded_has_no_body_to_replace(pr2_apartment_context):
    world, robot, extensions = pr2_apartment_context
    action = MoveTorsoAction(TorsoState.HIGH)
    goal = JointPositionList(
        goal_state=robot.get_torso().get_joint_state_by_type(TorsoState.LOW)
    )

    with pytest.raises(ActionNotExpanded):
        action.replace_action_body(goal)


def test_the_body_of_a_compiled_action_cannot_be_replaced(pr2_apartment_context):
    world, robot, extensions = pr2_apartment_context
    executor = simulated_executor(extensions)
    action = MoveTorsoAction(TorsoState.HIGH)
    executor.compile(statechart_of(executor, action))
    goal = JointPositionList(
        goal_state=robot.get_torso().get_joint_state_by_type(TorsoState.LOW)
    )

    with pytest.raises(StatechartAlreadyCompiledError):
        action.replace_action_body(goal)


def test_an_action_joining_a_compiled_statechart_runs_the_body_it_is_given_instead(
    pr2_apartment_context,
):
    world, robot, extensions = pr2_apartment_context
    executor = simulated_executor(extensions)
    statechart = statechart_of(executor, MoveTorsoAction(TorsoState.HIGH))
    executor.compile(statechart)
    action = MoveTorsoAction(TorsoState.LOW)
    goal = JointPositionList(
        goal_state=robot.get_torso().get_joint_state_by_type(TorsoState.LOW)
    )

    with statechart.modify():
        statechart.add_node(action)
        action.replace_action_body(goal)

    assert action.action_body is goal
    assert statechart.latest_compile_covers(goal)


# %% driving a differential drive


@pytest.mark.parametrize("build_executor", [simulated_executor, robot_executor])
def test_stretch_drives_with_its_differential_drive(
    stretch_apartment_context, build_executor
):
    world, robot, extensions = stretch_apartment_context
    executor = build_executor(
        rewriting_with(extensions, DriveStretchWithItsDifferentialDrive())
    )

    action = prepared(navigation_to(world), executor)

    assert_drives_differentially_to(action.action_body, action, robot)


def test_the_differential_drive_goal_takes_the_threshold_of_the_action(
    stretch_apartment_context,
):
    world, robot, extensions = stretch_apartment_context
    executor = robot_executor(
        rewriting_with(extensions, DriveStretchWithItsDifferentialDrive())
    )
    default_action = navigation_to(world)

    action = prepared(
        navigation_to(
            world, base_pose_threshold=10 * default_action.base_pose_threshold
        ),
        executor,
    )

    assert action.base_pose_threshold != default_action.base_pose_threshold
    assert_drives_differentially_to(action.action_body, action, robot)


def test_the_base_pose_threshold_defaults_to_the_one_of_the_differential_drive_goal(
    stretch_apartment_context,
):
    world, robot, extensions = stretch_apartment_context

    assert navigation_to(world).base_pose_threshold == (
        DifferentialDriveBaseGoal.threshold
    )


def test_stretch_drives_every_leg_of_a_path_with_its_differential_drive(
    stretch_apartment_context,
):
    world, robot, extensions = stretch_apartment_context
    target = Pose.from_xyz_rpy(2.0, 2.0, 0.0, reference_frame=world.root)
    unchanged = prepared(
        PathPlanningNavigateAction(target), simulated_executor(extensions)
    )
    executor = simulated_executor(
        rewriting_with(extensions, DriveStretchWithItsDifferentialDrive())
    )

    action = prepared(PathPlanningNavigateAction(target), executor)

    legs = action.action_body.nodes
    assert type(action.action_body) is Sequence
    assert [type(leg) for leg in legs] == [DifferentialDriveBaseGoal] * len(
        unchanged.action_body.nodes
    )
    assert all(leg.diff_drive_connection is robot.drive for leg in legs)
    assert all(leg.threshold == action.base_pose_threshold for leg in legs)
    np.testing.assert_allclose(legs[-1].goal_pose.to_np(), target.to_np())


def test_a_simulated_tiago_drives_with_its_differential_drive(tiago_context):
    world, robot, extensions = tiago_context
    executor = simulated_executor(
        rewriting_with(extensions, DriveSimulatedTiagoWithItsDifferentialDrive())
    )

    action = prepared(navigation_to(world), executor)

    assert_drives_differentially_to(action.action_body, action, robot)


def test_the_real_tiago_keeps_its_drive_goal(tiago_context):
    world, robot, extensions = tiago_context
    executor = robot_executor(rewriting_with(extensions, *every_base_transformation()))

    action = prepared(navigation_to(world), executor)

    goal = action.action_body
    assert type(goal) is CartesianPose
    assert goal.root_link is world.root
    assert goal.tip_link is robot.root


@pytest.mark.parametrize(
    "build_executor, goal_type",
    [(simulated_executor, SetOdometry), (robot_executor, CartesianPose)],
)
def test_a_robot_of_another_type_keeps_its_drive_goal(
    pr2_apartment_context, build_executor, goal_type
):
    world, robot, extensions = pr2_apartment_context
    executor = build_executor(rewriting_with(extensions, *every_base_transformation()))

    action = prepared(navigation_to(world), executor)

    assert type(action.action_body) is goal_type


def test_stretch_keeps_its_drive_goal_without_the_transformation(
    stretch_apartment_context,
):
    world, robot, extensions = stretch_apartment_context

    action = prepared(navigation_to(world), robot_executor(extensions))

    assert type(action.action_body) is CartesianPose


def test_a_simulated_stretch_arrives_driving_with_its_differential_drive(
    stretch_apartment_context,
):
    world, robot, extensions = stretch_apartment_context
    executor = simulated_executor(
        rewriting_with(extensions, DriveStretchWithItsDifferentialDrive())
    )
    action = navigation_to(world)
    executor.compile(statechart_of(executor, action))

    executor.execute()

    np.testing.assert_allclose(
        robot.root.global_pose.to_np(),
        robot.mobile_base.pose_facing(action.target_location).to_np(),
        atol=2 * action.base_pose_threshold,
    )


def test_a_simulated_stretch_drives_differentially_to_a_pose_chosen_while_running(
    stretch_apartment_context,
):
    world, robot, extensions = stretch_apartment_context
    executor = simulated_executor(
        rewriting_with(extensions, DriveStretchWithItsDifferentialDrive())
    )
    navigation = UnderspecifiedNode(
        statement=a(NavigateAction)(
            target_location=variable_from([navigation_to(world).target_location])
        )
    )
    executor.compile(statechart_of(executor, navigation))

    executor.execute()

    [action] = navigation.chosen_actions
    assert_drives_differentially_to(action.action_body, action, robot)


def test_a_drive_chosen_while_running_is_watched_for_stalling_as_it_is_driven(
    stretch_apartment_context,
):
    """
    The transformation replaces the body of the chosen drive, so the monitor giving up
    on a stalled attempt has to watch the tasks of the body that runs.
    """
    world, robot, extensions = stretch_apartment_context
    executor = simulated_executor(
        rewriting_with(extensions, DriveStretchWithItsDifferentialDrive())
    )
    navigation = UnderspecifiedNode(
        statement=a(NavigateAction)(
            target_location=variable_from([navigation_to(world).target_location])
        )
    )
    executor.compile(statechart_of(executor, navigation))

    executor.execute()

    [attempt] = navigation.children
    [stalled] = attempt.failure_monitors
    [action] = navigation.chosen_actions
    assert stalled.monitored_tasks == [
        node for node in action.descendants if isinstance(node, ConvergingTask)
    ]


# %% closing a container


def close_action(world: World, robot: AbstractRobot) -> CloseAction:
    """
    :return: An action closing a container of the apartment with the arm of `robot`.
    """
    handle = world.get_semantic_annotations_by_type(Handle)[0]
    return CloseAction(handle.grasp_candidates()[0], robot.all_arms[0])


def closing_step_of(action: CloseAction) -> StatechartNode:
    """
    :return: The step of an expanded close action between grasping the handle and
        letting go of it.
    """
    grasp, closing_step, release = action.action_body.nodes
    return closing_step


def test_a_simulated_stretch_stays_in_front_of_the_container_it_closes(
    stretch_apartment_context,
):
    world, robot, extensions = stretch_apartment_context
    unchanged = prepared(close_action(world, robot), simulated_executor(extensions))
    default_close = closing_step_of(unchanged)
    executor = simulated_executor(
        rewriting_with(extensions, KeepStretchInFrontOfTheContainerItCloses())
    )

    action = prepared(close_action(world, robot), executor)

    closing_step = closing_step_of(action)
    tool_frame = action.arm.end_effector.tool_frame
    assert type(closing_step) is Parallel
    holding, facing, close = closing_step.nodes
    assert type(holding) is CartesianPose
    assert holding.root_link is action.grasp.graspable.root
    assert holding.tip_link is tool_frame
    np.testing.assert_allclose(holding.goal_pose.to_np(), Pose().to_np())
    assert holding.goal_pose.reference_frame is tool_frame
    assert type(facing) is AlignPlanes
    assert facing.root_link is world.root
    assert facing.tip_link is robot.root
    np.testing.assert_allclose(facing.goal_normal.to_np()[:3], [1, 0, 0])
    assert facing.goal_normal.reference_frame is action.grasp.graspable.root
    np.testing.assert_allclose(facing.tip_normal.to_np()[:3], [0, -1, 0])
    assert facing.tip_normal.reference_frame is robot.root
    assert type(close) is Close
    assert close.tip_link is default_close.tip_link
    assert close.environment_link is default_close.environment_link
    assert close.goal_joint_state == default_close.goal_joint_state


def test_the_real_stretch_closes_a_container_unchanged(stretch_apartment_context):
    world, robot, extensions = stretch_apartment_context
    executor = robot_executor(
        rewriting_with(extensions, KeepStretchInFrontOfTheContainerItCloses())
    )

    action = prepared(close_action(world, robot), executor)

    assert type(closing_step_of(action)) is Close


def test_a_robot_of_another_type_closes_a_container_unchanged(pr2_apartment_context):
    world, robot, extensions = pr2_apartment_context
    executor = simulated_executor(
        rewriting_with(extensions, KeepStretchInFrontOfTheContainerItCloses())
    )

    action = prepared(close_action(world, robot), executor)

    assert type(closing_step_of(action)) is Close

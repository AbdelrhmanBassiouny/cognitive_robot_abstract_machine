from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest
from typing_extensions import List, Optional, Type

from coraplex.plans.context_extensions import RobotAccess
from coraplex.plans.executors import PlanExecutor
from coraplex.robot_plans.actions.base import Action
from coraplex.robot_plans.actions.core.exceptions import WidthBeyondGripperOpening
from coraplex.datastructures.trajectory import PoseTrajectory
from coraplex.robot_plans.actions.core.navigation import LookAtAction, NavigateAction
from coraplex.robot_plans.actions.core.robot_body import (
    FollowToolCenterPointPathAction,
    MoveFingersToWidthAction,
    MoveManipulatorAction,
    MoveTorsoAction,
    ParkArmsAction,
    SetGripperAction,
)
from cramph.composites import Parallel, Sequence
from cramph.data_types import LifeCycleValues, ObservationStateValues
from cramph.exceptions import (
    CompositeNodeWithoutChildrenError,
    NodesMissingContextExtensionsError,
)
from cramph.executor import StatechartExecutor
from cramph.node import EndStatechart, StatechartNode
from cramph.nodes_for_testing import (
    NodeFailingOnObservingFalse,
    NodeObservingAFixedValue,
    NodeSucceedingOnObservingTrue,
)
from cramph.statechart import Statechart
from giskardpy.motion_statechart.goals.collision_avoidance import (
    UpdateTemporaryCollisionRules,
)
from giskardpy.motion_statechart.goals.gripper import MoveGripper
from giskardpy.motion_statechart.data_types import DefaultWeights
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianPose,
    DistanceAlongAxis,
    HoldPose,
)
from giskardpy.motion_statechart.tasks.pointing import Pointing, PointingBeside
from giskardpy.motion_statechart.monitors.overwrite_state_monitors import SetOdometry
from krrood.patterns.field_metadata import ParameterMetadata
from giskardpy.motion_statechart.tasks.joint_tasks import (
    JointPositionList,
    JointVelocityLimit,
)
from semantic_digital_twin.datastructures.definitions import GripperState, TorsoState
from semantic_digital_twin.spatial_types.spatial_types import Pose
from ..conftest import physically_simulated_executor
from ...plan_running import (
    robot_executor,
    run_plan,
    simulated_executor,
    statechart_of,
)
from cramph.context import ContextExtension, StatechartContext

# %% a body handed in, so expansion is exercised without a robot


@dataclass(eq=False, repr=False, kw_only=True)
class ActionRunningHandedInSteps(Action):
    """
    An action whose body is handed to it rather than derived from a robot, so that
    expanding and running an action can be exercised on its own.
    """

    steps: List[StatechartNode] = field(default_factory=list)
    """
    The children of this action, in order.
    """

    def create_action_body(self) -> StatechartNode:
        return Sequence(nodes=list(self.steps))


def _succeeding(name: str) -> NodeSucceedingOnObservingTrue:
    """
    :return: A node that ends itself successfully as soon as it observes.
    """
    return NodeSucceedingOnObservingTrue(
        name=name, observation=ObservationStateValues.TRUE
    )


def _failing(name: str) -> NodeFailingOnObservingFalse:
    """
    :return: A node that declares itself failed as soon as it observes.
    """
    return NodeFailingOnObservingFalse(
        name=name, observation=ObservationStateValues.FALSE
    )


def _expanded(
    action: Action,
    extensions: List[ContextExtension],
    executor: Optional[PlanExecutor] = None,
) -> Statechart:
    """
    Adds `action` to a statechart, which expands it.

    :param executor: The executor whose context the statechart is built in, a simulated
        one by default.
    :return: The statechart holding the expanded action.
    """
    if executor is None:
        executor = simulated_executor(extensions)
    return statechart_of(executor, action)


def _nodes_of_type(
    action: Action, node_type: Type[StatechartNode]
) -> List[StatechartNode]:
    """
    :return: Every node of `node_type` the expanded `action` runs, in tree order.
    """
    return [node for node in action.descendants if isinstance(node, node_type)]


def _run_until(statechart: Statechart, end: EndStatechart) -> None:
    """
    Compiles `statechart` and ticks it until `end` ends it.
    """
    statechart.add_node(end)
    executor = StatechartExecutor(context=statechart.context)
    executor.compile(statechart)
    executor.tick_until_end(timeout=100)


# %% an action is a statechart node


def test_action_runs_its_steps_as_one_sequence(simple_pr2_context):
    """
    An action's body is a sequence of exactly the nodes it names.
    """
    _, _, extensions = simple_pr2_context
    steps = [_succeeding("first"), _succeeding("second")]
    action = ActionRunningHandedInSteps(steps=steps)

    _expanded(action, extensions)

    [body] = action.children
    assert isinstance(body, Sequence)
    assert body.nodes == steps


@dataclass(eq=False, repr=False, kw_only=True)
class ActionRunningOneNode(Action):
    """
    An action whose body is a single node rather than a sequence of steps.
    """

    node: StatechartNode
    """
    The child of this action.
    """

    def create_action_body(self) -> StatechartNode:
        return self.node


def test_an_action_has_no_body_before_it_is_expanded():
    assert ActionRunningHandedInSteps(steps=[]).action_body is None


def test_an_action_needs_the_robot_performing_it(simple_pr2_context):
    world, _, _ = simple_pr2_context
    statechart = Statechart(context=StatechartContext(world=world))
    action = ActionRunningHandedInSteps(steps=[_succeeding("only")])

    with pytest.raises(NodesMissingContextExtensionsError) as raised:
        statechart.add_node(action)

    assert raised.value.nodes_by_missing_extension == {RobotAccess: [action]}


def test_an_action_runs_the_body_it_created(simple_pr2_context):
    _, _, extensions = simple_pr2_context
    action = ActionRunningHandedInSteps(steps=[_succeeding("only step")])

    _expanded(action, extensions)

    assert action.children == [action.action_body]


def test_an_action_body_can_be_a_single_node(simple_pr2_context):
    _, _, extensions = simple_pr2_context
    step = _succeeding("only step")
    action = ActionRunningOneNode(node=step)
    statechart = _expanded(action, extensions)

    _run_until(statechart, EndStatechart.when_true(action))

    assert action.action_body is step
    assert action.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_an_action_whose_body_its_owner_decides_succeeds_once_the_body_arrives(
    simple_pr2_context,
):
    """
    A single task never ends on its own, so the action ends it once it is at its goal.
    """
    _, _, extensions = simple_pr2_context
    task = NodeObservingAFixedValue(
        name="task", observation=ObservationStateValues.TRUE
    )
    action = ActionRunningOneNode(node=task)
    statechart = _expanded(action, extensions)

    _run_until(statechart, EndStatechart.when_true(action))

    assert action.action_body is task
    assert task.life_cycle_state == LifeCycleValues.SUCCEEDED
    assert action.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_an_action_whose_body_its_owner_decides_waits_while_the_body_is_away(
    simple_pr2_context,
):
    """
    A task that has not arrived yet observes False, which is not a failure of the
    action running it.
    """
    _, _, extensions = simple_pr2_context
    task = NodeObservingAFixedValue(
        name="task", observation=ObservationStateValues.FALSE
    )
    action = ActionRunningOneNode(node=task)
    statechart = _expanded(action, extensions)
    statechart.add_node(EndStatechart.when_true(action))
    executor = StatechartExecutor(context=statechart.context)
    executor.compile(statechart)

    for _ in range(3):
        executor.tick()

    assert action.life_cycle_state == LifeCycleValues.RUNNING


def test_action_succeeds_once_its_last_step_succeeded(simple_pr2_context):
    """
    An action ends successfully when the sequence it runs does.
    """
    _, _, extensions = simple_pr2_context
    action = ActionRunningHandedInSteps(steps=[_succeeding("only step")])
    statechart = _expanded(action, extensions)

    _run_until(statechart, EndStatechart.when_true(action))

    assert action.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_action_fails_once_a_step_ended_without_succeeding(simple_pr2_context):
    """
    A step that cannot arrive fails the action rather than leaving it waiting.
    """
    _, _, extensions = simple_pr2_context
    action = ActionRunningHandedInSteps(steps=[_failing("step that gives up")])
    statechart = _expanded(action, extensions)

    _run_until(statechart, EndStatechart.when_failed(action))

    assert action.life_cycle_state == LifeCycleValues.FAILED


def test_action_without_steps_is_rejected(simple_pr2_context):
    """
    An action that names no node to run is a mistake, not an empty success.
    """
    _, _, extensions = simple_pr2_context
    statechart = _expanded(ActionRunningHandedInSteps(steps=[]), extensions)

    with pytest.raises(CompositeNodeWithoutChildrenError):
        statechart.compile()


def test_action_parameters_leave_out_statechart_machinery(simple_pr2_context):
    """
    Only what the action was parameterized with counts as its parameters.
    """
    action = MoveTorsoAction(torso_state=TorsoState.HIGH)

    assert action.designator_parameter == {"torso_state": TorsoState.HIGH}


@dataclass(eq=False, repr=False, kw_only=True)
class ActionWithKeywordOnlyParameter(ActionRunningHandedInSteps):
    """
    An action taking one of its parameters by keyword only.
    """

    speed: float = 1.0
    """
    A parameter that can only be passed by keyword.
    """


@dataclass(eq=False, repr=False, kw_only=True)
class ActionWithHelperField(ActionRunningHandedInSteps):
    """
    An action carrying a field its caller sets that is not one of its parameters.
    """

    helper: int = field(
        default=0, metadata=ParameterMetadata(is_parameter=False).as_dict()
    )
    """
    A value the action needs that does not describe what it does.
    """


def test_a_keyword_only_field_is_a_parameter():
    action = ActionWithKeywordOnlyParameter(speed=2.0)

    assert action.designator_parameter == {"steps": [], "speed": 2.0}


def test_the_name_of_an_action_is_not_a_parameter():
    action = MoveTorsoAction(torso_state=TorsoState.HIGH, name="lift")

    assert action.designator_parameter == {"torso_state": TorsoState.HIGH}


def test_a_field_marked_as_no_parameter_is_left_out():
    action = ActionWithHelperField(helper=3)

    assert action.designator_parameter == {"steps": []}


# %% the converted actions


def test_move_torso_runs_the_joint_goal_of_the_requested_state(
    simple_pr2_context,
):
    """
    Moving the torso drives it to the joint state that torso state stands for.
    """
    _, robot, extensions = simple_pr2_context
    action = MoveTorsoAction(torso_state=TorsoState.HIGH)

    _expanded(action, extensions)

    [joint_goal] = _nodes_of_type(action, JointPositionList)
    assert joint_goal.goal_state == robot.get_torso().get_joint_state_by_type(
        TorsoState.HIGH
    )


def test_set_gripper_drives_the_gripper_it_names(simple_pr2_context):
    """
    Setting a gripper drives that gripper, with one goal.
    """
    _, robot, extensions = simple_pr2_context
    action = SetGripperAction(
        gripper=robot.left_arm.end_effector, motion=GripperState.OPEN
    )

    _expanded(action, extensions)

    [goal] = _nodes_of_type(action, MoveGripper)
    assert goal.end_effector is robot.left_arm.end_effector


def test_park_arms_caps_joint_velocity_only_when_asked(simple_pr2_context):
    """
    The velocity cap is a limit run alongside the park goal, not always present.
    """
    _, robot, extensions = simple_pr2_context
    capped = ParkArmsAction(arms=robot.all_arms, max_joint_velocity=0.1)
    uncapped = ParkArmsAction(arms=robot.all_arms)

    _expanded(capped, extensions)
    _expanded(uncapped, extensions)

    [limit] = _nodes_of_type(capped, JointVelocityLimit)
    assert limit.max_velocity == 0.1
    assert _nodes_of_type(capped, Parallel) != []
    assert _nodes_of_type(uncapped, JointVelocityLimit) == []


def test_look_at_points_the_default_camera(simple_pr2_context):
    """
    Looking somewhere aims the robot's own camera, and runs nothing else.
    """
    _, robot, extensions = simple_pr2_context
    action = LookAtAction(target=Pose())

    _expanded(action, extensions)

    [pointing] = _nodes_of_type(action, Pointing)
    assert pointing.tip_link == robot.get_default_camera().root


def test_looking_beside_a_target_takes_sideways_from_the_robots_base(
    simple_pr2_context,
):
    """
    Left and right of a target are as seen from where the robot stands.
    """
    _, robot, extensions = simple_pr2_context
    action = LookAtAction(target=Pose(), sideways_offset=0.5)

    _expanded(action, extensions)

    [pointing] = _nodes_of_type(action, PointingBeside)
    assert pointing.viewpoint == robot.root
    assert pointing.sideways_offset == action.sideways_offset


def test_following_a_path_runs_one_goal_per_waypoint(simple_pr2_context):
    """
    Every waypoint of the path becomes a goal of its own, in order.
    """
    _, robot, extensions = simple_pr2_context
    waypoints = [Pose(), Pose(), Pose()]
    action = FollowToolCenterPointPathAction(
        target_locations=PoseTrajectory(waypoints), arm=robot.left_arm
    )

    _expanded(action, extensions)

    assert len(_nodes_of_type(action, CartesianPose)) == len(waypoints)


def test_moving_the_manipulator_relaxes_collisions_only_when_allowed(
    simple_pr2_context,
):
    """
    The gripper is only let through its surroundings when the caller asks.
    """
    _, robot, extensions = simple_pr2_context
    end_effector = robot.left_arm.end_effector
    allowed = MoveManipulatorAction(
        target_pose=Pose(), end_effector=end_effector, allow_gripper_collision=True
    )
    forbidden = MoveManipulatorAction(
        target_pose=Pose(), end_effector=end_effector, allow_gripper_collision=False
    )

    _expanded(allowed, extensions)
    _expanded(forbidden, extensions)

    assert len(_nodes_of_type(allowed, UpdateTemporaryCollisionRules)) == 1
    assert _nodes_of_type(forbidden, UpdateTemporaryCollisionRules) == []
    assert len(_nodes_of_type(forbidden, CartesianPose)) == 1


def test_navigating_drives_the_base_towards_what_it_should_face(
    simple_pr2_context,
):
    """
    Navigating commands the base pose, and runs nothing else.
    """
    _, robot, extensions = simple_pr2_context
    action = NavigateAction(target_location=Pose())

    _expanded(action, extensions, robot_executor(extensions))

    [drive] = _nodes_of_type(action, CartesianPose)
    assert drive.tip_link == robot.root


def test_navigating_writes_the_odometry_when_simulated(simple_pr2_context):
    """
    A simulated run has no drive to follow a pose, so it sets the odometry itself.
    """
    _, _, extensions = simple_pr2_context
    action = NavigateAction(target_location=Pose())

    _expanded(action, extensions)

    assert len(_nodes_of_type(action, SetOdometry)) == 1
    assert _nodes_of_type(action, CartesianPose) == []


def test_navigating_drives_the_base_when_physically_simulated(simple_pr2_context):
    """
    A robot whose wheels have to carry it cannot be put at a pose by saying so, which is
    why performing in physics is told apart from performing kinematically.
    """
    _, robot, extensions = simple_pr2_context
    action = NavigateAction(target_location=Pose())

    _expanded(action, extensions, physically_simulated_executor(extensions))

    assert _nodes_of_type(action, SetOdometry) == []
    [drive] = _nodes_of_type(action, CartesianPose)
    assert drive.tip_link == robot.root


# %% a robot that does not move its whole body stands still while it moves an arm


@pytest.fixture
def full_body_controlled_pr2(simple_pr2_context):
    """
    The PR2 context with the PR2 allowed to move its whole body, restored afterwards:
    the world snapshot does not cover this setting.
    """
    world, robot, extensions = simple_pr2_context
    with world.modify_world():
        robot.mobile_base.full_body_controlled = True
    yield world, robot, extensions
    with world.modify_world():
        robot.mobile_base.full_body_controlled = False


def arm_and_look_actions(robot) -> List[Action]:
    """
    :return: One of every action that moves an arm or the head while the base is meant
        to stand.
    """
    end_effector = robot.left_arm.end_effector
    return [
        MoveManipulatorAction(
            target_pose=Pose(), end_effector=end_effector, allow_gripper_collision=False
        ),
        FollowToolCenterPointPathAction(
            target_locations=PoseTrajectory([Pose()]), arm=robot.left_arm
        ),
        LookAtAction(target=Pose()),
    ]


def test_moving_an_arm_or_looking_holds_the_base_of_a_robot_that_stands_still(
    simple_pr2_context,
):
    """
    A goal relative to the robot is bound when it starts, so a base that collision
    avoidance pushes afterwards carries the goal away from its target.
    """
    world, robot, extensions = simple_pr2_context
    assert not robot.mobile_base.full_body_controlled

    for action in arm_and_look_actions(robot):
        _expanded(action, extensions)

        [hold_base] = _nodes_of_type(action, HoldPose)
        assert hold_base.root_link == world.root
        assert hold_base.tip_link == robot.root
        assert hold_base.weight == DefaultWeights.WEIGHT_ABOVE_COLLISION_AVOIDANCE


def test_moving_an_arm_or_looking_leaves_a_full_body_controlled_base_free(
    full_body_controlled_pr2,
):
    """
    A robot that may move its whole body drives while it reaches, so its base is not
    held.
    """
    world, robot, extensions = full_body_controlled_pr2

    for action in arm_and_look_actions(robot):
        _expanded(action, extensions)

        assert _nodes_of_type(action, HoldPose) == []


# %% sending the fingers to a width


def test_fingers_sent_to_a_width_are_given_the_distance_between_their_facing_points(
    simple_pr2_context,
):
    """
    The distance between the fingertips is what Giskard is given, so it finds the joint
    positions that realise it rather than being told them.
    """
    _, robot, extensions = simple_pr2_context
    gripper = robot.left_arm.end_effector
    action = MoveFingersToWidthAction(gripper=gripper, width=0.04)

    _expanded(action, extensions, physically_simulated_executor(extensions))

    goal = action.action_body
    assert isinstance(goal, DistanceAlongAxis)
    assert goal.reference_point.reference_frame is gripper.finger.tip
    assert goal.tip_point.reference_frame is gripper.thumb.tip
    assert goal.distance == action.width


def test_a_squeeze_sends_the_fingers_past_the_width(simple_pr2_context):
    _, robot, extensions = simple_pr2_context
    gripper = robot.left_arm.end_effector
    width = 0.04
    squeeze = 0.001
    touching = MoveFingersToWidthAction(gripper=gripper, width=width)
    pressing = MoveFingersToWidthAction(gripper=gripper, width=width, squeeze=squeeze)

    _expanded(touching, extensions, physically_simulated_executor(extensions))
    _expanded(pressing, extensions, physically_simulated_executor(extensions))

    assert pressing.action_body.distance == pytest.approx(
        touching.action_body.distance - 2 * squeeze
    )


def test_hinged_fingers_sent_to_a_width_stand_that_far_apart(stretch_apartment_context):
    """
    A Stretch's fingers swing on hinges, so their tips stand a width apart without one
    ever standing straight across from the other.
    """
    _, robot, extensions = stretch_apartment_context
    (arm,) = robot.all_arms
    gripper = arm.end_effector
    action = MoveFingersToWidthAction(gripper=gripper, width=0.04)

    run_plan(action, extensions)

    assert gripper.fingertips.separation == pytest.approx(
        action.width, abs=action.threshold
    )


def test_fingers_are_not_sent_wider_than_their_gripper_opens(simple_pr2_context):
    _, robot, extensions = simple_pr2_context
    gripper = robot.left_arm.end_effector
    action = MoveFingersToWidthAction(
        gripper=gripper, width=gripper.separation_when_open + 0.01
    )

    with pytest.raises(WidthBeyondGripperOpening):
        _expanded(action, extensions, physically_simulated_executor(extensions))


def test_fingers_may_be_sent_as_wide_as_their_gripper_opens(simple_pr2_context):
    _, robot, extensions = simple_pr2_context
    gripper = robot.left_arm.end_effector
    action = MoveFingersToWidthAction(
        gripper=gripper, width=gripper.separation_when_open
    )

    _expanded(action, extensions, physically_simulated_executor(extensions))

    assert isinstance(action.action_body, DistanceAlongAxis)

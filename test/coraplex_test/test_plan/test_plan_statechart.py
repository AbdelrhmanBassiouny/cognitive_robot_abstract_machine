"""
Tests for running a plan as one statechart, see
:class:`~coraplex.plans.executors.PlanExecutor`.
"""

import pytest
import json
from dataclasses import dataclass, field

from typing_extensions import Iterator, List

from coraplex.exceptions import MotionDidNotFinish
from coraplex.locations.base import Location
from coraplex.plans.failures import EmptyUnderspecified
from coraplex.plans.underspecified import UnderspecifiedNode
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from coraplex.plans import executors
from cramph.composites import (
    ChildChooser,
    CompositeNodeChoosingItsChild,
    PausedUntilTrue,
    Sequence,
)
from cramph.data_types import LifeCycleValues, ObservationStateValues
from cramph.executor import StatechartExecutor
from cramph.nodes_for_testing import ConstTrueNode, NodeFailingOnObservingFalse
from cramph.statechart import Statechart
from cramph.world_modification_nodes import MoveBranch
from giskardpy.motion_control import MotionControl
from giskardpy.motion_statechart.graph_node import EndMotion
from krrood.adapters.json_serializer import from_json, to_json
from krrood.entity_query_language.factories import a, variable
from semantic_digital_twin.adapters.world_entity_kwargs_tracker import (
    WorldEntityWithIDKwargsTracker,
)
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.semantic_annotations.semantic_annotations import Milk
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from ...plan_running import robot_executor, run_plan, simulated_executor, statechart_of

# %% helpers


def _pose_in_front_of_the_robot(world, robot) -> Pose:
    """
    :return: A pose in the world frame, a few centimetres in front of where the robot
        stands now.
    """
    return world.transform(
        Pose.from_xyz_rpy(x=0.05, reference_frame=robot.root), world.root
    )


@dataclass
class RecordingLocationInFrontOfTheRobot(Location):
    """
    A location in front of the robot that records, each time it is sampled, whether the
    torso stood high at that moment.
    """

    world: World
    """
    The world the robot stands in.
    """

    robot: AbstractRobot
    """
    The robot the location is in front of.
    """

    torso_high_when_sampled: List[bool] = field(default_factory=list)
    """
    Whether the torso stood high, once per sampling.
    """

    def candidates(self) -> Iterator[Pose]:
        torso_high = self.robot.get_torso().get_joint_state_by_type(TorsoState.HIGH)
        self.torso_high_when_sampled.append(torso_high.is_achieved())
        yield _pose_in_front_of_the_robot(self.world, self.robot)


# %% one statechart per plan


def test_a_plan_grounding_an_action_mid_sequence_runs_as_one_statechart(
    pr2_apartment_context,
):
    world, robot, extensions = pr2_apartment_context
    torso = MoveTorsoAction(TorsoState.HIGH)
    plan = Sequence(
        [
            torso,
            UnderspecifiedNode(
                statement=a(NavigateAction)(
                    target_location=variable(
                        Pose, domain=[_pose_in_front_of_the_robot(world, robot)]
                    )
                )
            ),
        ]
    )

    run_plan(plan, extensions)

    statechart: Statechart = plan.statechart
    navigate = plan.nodes[1].chosen_actions[-1]
    assert isinstance(navigate, NavigateAction)
    assert navigate.statechart is statechart
    assert torso.statechart is statechart
    assert len(statechart.get_nodes_by_type(EndMotion)) == 1
    assert plan.life_cycle_state == LifeCycleValues.SUCCEEDED


def test_an_underspecified_action_is_grounded_against_the_world_the_steps_before_left(
    pr2_apartment_context,
):
    world, robot, extensions = pr2_apartment_context
    torso_high = robot.get_torso().get_joint_state_by_type(TorsoState.HIGH)
    assert not torso_high.is_achieved()
    location = RecordingLocationInFrontOfTheRobot(world=world, robot=robot)

    plan = Sequence(
        [
            MoveTorsoAction(TorsoState.HIGH),
            UnderspecifiedNode(
                statement=a(NavigateAction)(
                    target_location=variable(Pose, domain=location)
                )
            ),
        ]
    )

    run_plan(plan, extensions)

    assert location.torso_high_when_sampled == [True]


def test_a_branch_moved_mid_plan_follows_its_new_parent(pr2_apartment_context):
    world, robot, extensions = pr2_apartment_context
    milk = world.get_body_by_name("milk.stl")
    tool_frame = robot.left_arm.end_effector.tool_frame
    height_before = milk.global_pose.z

    plan = Sequence(
        [
            MoveTorsoAction(TorsoState.LOW),
            MoveBranch(body=milk, new_parent=tool_frame),
            MoveTorsoAction(TorsoState.HIGH),
        ]
    )
    run_plan(plan, extensions)

    assert milk.parent_connection.parent is tool_frame
    assert milk.global_pose.z > height_before


# %% actions as statechart nodes


def test_actions_with_the_same_parameters_are_different_nodes():
    first = MoveTorsoAction(TorsoState.HIGH)
    second = MoveTorsoAction(TorsoState.HIGH)

    assert first != second


def test_a_place_finds_the_grasp_of_the_pick_up_before_it(pr2_apartment_context):
    world, robot, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    pick_up = PickUpAction(milk.grasp_candidates()[0], robot.left_arm)
    place = PlaceAction(
        milk, Pose.from_xyz_rpy(0.8, -1.9, 0.7, reference_frame=world.root)
    )
    statechart = Statechart(context=simulated_executor(extensions).context)

    statechart.add_node(Sequence([pick_up, place]))

    assert statechart.get_preceding_node_by_type(place, PickUpAction) is pick_up


def test_a_place_below_a_pausing_composite_finds_the_pick_up_before_that(
    pr2_apartment_context,
):
    world, robot, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    pick_up = PickUpAction(milk.grasp_candidates()[0], robot.left_arm)
    place = PlaceAction(
        milk, Pose.from_xyz_rpy(0.8, -1.9, 0.7, reference_frame=world.root)
    )
    paused_place = PausedUntilTrue(monitor=ConstTrueNode(), monitored_node=place)
    statechart = Statechart(context=simulated_executor(extensions).context)

    statechart.add_node(Sequence([pick_up, paused_place]))

    assert statechart.get_preceding_node_by_type(place, PickUpAction) is pick_up


# %% running on the robot


@dataclass
class GiskardWrapperRecordingTheGoal:
    """
    Stands in for the connection to Giskard, recording what it is asked to execute.
    """

    executed: List[Statechart] = field(default_factory=list)
    """
    Every statechart sent, in order.
    """

    child_choosers: List[ChildChooser] = field(default_factory=list)
    """
    The chooser handed along with every statechart.
    """

    def execute(self, motion_statechart: Statechart, child_chooser: ChildChooser):
        self.executed.append(motion_statechart)
        self.child_choosers.append(child_chooser)


def test_an_underspecified_node_is_sent_as_a_node_choosing_its_child(
    pr2_apartment_context,
):
    """
    Giskard receives the children the client chooses, so it needs nothing but the node
    itself, and not the statement it is grounded from.
    """
    world, robot, extensions = pr2_apartment_context
    node = UnderspecifiedNode(statement=a(NavigateAction)(target_location=...))

    received = from_json(json.loads(json.dumps(to_json(node))))

    assert type(received) is CompositeNodeChoosingItsChild
    assert received.name == node.name


def test_a_plan_on_the_robot_is_sent_once_with_the_chooser_grounding_its_actions(
    pr2_apartment_context, monkeypatch
):
    world, robot, extensions = pr2_apartment_context
    giskard = GiskardWrapperRecordingTheGoal()
    monkeypatch.setattr(executors, "GiskardWrapper", lambda ros_node, world: giskard)
    plan = Sequence(
        [
            MoveTorsoAction(TorsoState.HIGH),
            UnderspecifiedNode(
                statement=a(NavigateAction)(
                    target_location=variable(
                        Pose, domain=[_pose_in_front_of_the_robot(world, robot)]
                    )
                )
            ),
        ]
    )
    executor = robot_executor(extensions)

    executor.compile(statechart_of(executor, plan))
    executor.execute()

    [statechart] = giskard.executed
    assert plan.statechart is statechart
    [chooser] = giskard.child_choosers
    assert chooser is executor.child_chooser


@dataclass
class GiskardTickingTheGoalUntilItEnded:
    """
    Stands in for Giskard, ticking what it is asked to execute until the statechart
    ended, which is the only way Giskard's control loop finishes a goal by itself.
    """

    tick_limit: int = 50
    """
    The number of ticks after which a statechart that did not end is given up on.
    """

    def execute(self, motion_statechart: Statechart, child_chooser: ChildChooser):
        giskard = StatechartExecutor(
            context=motion_statechart.context, extensions=[MotionControl()]
        )
        giskard.compile(motion_statechart)
        giskard.tick_until_end(timeout=self.tick_limit)


def test_a_plan_that_fails_on_the_robot_raises_motion_did_not_finish(
    pr2_apartment_context, monkeypatch
):
    world, robot, extensions = pr2_apartment_context
    monkeypatch.setattr(
        executors,
        "GiskardWrapper",
        lambda ros_node, world: GiskardTickingTheGoalUntilItEnded(),
    )
    plan = NodeFailingOnObservingFalse(observation=ObservationStateValues.FALSE)
    executor = robot_executor(extensions)
    executor.compile(statechart_of(executor, plan))

    with pytest.raises(MotionDidNotFinish) as failure:
        executor.execute()

    assert failure.value.unfinished_motions == [plan]
    assert plan.life_cycle_state == LifeCycleValues.FAILED


def test_an_underspecified_action_out_of_candidates_on_the_robot_says_it_is_empty(
    pr2_apartment_context, monkeypatch
):
    world, robot, extensions = pr2_apartment_context
    monkeypatch.setattr(
        executors,
        "GiskardWrapper",
        lambda ros_node, world: GiskardTickingTheGoalUntilItEnded(),
    )
    plan = UnderspecifiedNode(
        statement=a(NavigateAction)(target_location=variable(Pose, domain=[]))
    )
    executor = robot_executor(extensions)
    executor.compile(statechart_of(executor, plan))

    with pytest.raises(EmptyUnderspecified) as failure:
        executor.execute()

    assert failure.value.node is plan


def test_an_expanded_action_is_received_with_the_nodes_it_runs(pr2_apartment_context):
    """
    A receiver does not expand the nodes of a statechart again, so an action has to
    arrive knowing the sequence it runs.
    """
    world, robot, extensions = pr2_apartment_context
    sent = Statechart(context=simulated_executor(extensions).context)
    sent.add_node(action := MoveTorsoAction(TorsoState.HIGH))

    received = Statechart.from_json(
        json.loads(json.dumps(sent.to_json())),
        context=simulated_executor(extensions).context,
        **WorldEntityWithIDKwargsTracker.from_world(world).create_kwargs(),
    )

    received_action = received.get_node_by_index(action.index)
    assert received_action.action_body is received.get_node_by_index(
        action.action_body.index
    )
